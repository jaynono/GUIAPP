import PySimpleGUI as sg
import requests
import time
import json
import csv
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import warnings
import re
import os
import traceback
import numpy as np
from datetime import timedelta

# FutureWarning を抑制
warnings.simplefilter(action='ignore', category=FutureWarning)

def debug_print(window, message):
    window['OUTPUT'].print(f"DEBUG: {message}")
    window.refresh()

def 動画ID抽出(url):
    マッチ = re.search(r'videos/(\d+)', url)
    if マッチ:
        return マッチ.group(1)
    else:
        raise ValueError("無効なTwitch URLです。有効な動画URLを入力してください。")

def JSONデータ取得(動画ID, カーソル=None):
    if カーソル is None:
        return json.dumps([
            {
                "operationName": "VideoCommentsByOffsetOrCursor",
                "variables": {
                    "videoID": 動画ID,
                    "contentOffsetSeconds": 0
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
                    }
                }
            }
        ])
    else:
        return json.dumps([
            {
                "operationName": "VideoCommentsByOffsetOrCursor",
                "variables": {
                    "videoID": 動画ID,
                    "cursor": カーソル
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
                    }
                }
            }
        ])

def タイムスタンプ整形(秒数):
    return str(timedelta(seconds=int(秒数)))

def コメント処理(データ, csvライター):
    try:
        コメント一覧 = データ[0]['data']['video']['comments']['edges']
        for コメント in コメント一覧:
            メッセージ = コメント['node']['message']['fragments'][0]['text']
            タイムスタンプ秒 = コメント['node']['contentOffsetSeconds']
            整形済みタイムスタンプ = タイムスタンプ整形(タイムスタンプ秒)
            ユーザー = コメント['node']['commenter']['displayName']
            csvライター.writerow([整形済みタイムスタンプ, タイムスタンプ秒, ユーザー, メッセージ])
        次ページあり = データ[0]['data']['video']['comments']['pageInfo']['hasNextPage']
        次カーソル = コメント一覧[-1]['cursor'] if 次ページあり else None
        return 次ページあり, 次カーソル
    except (KeyError, IndexError, TypeError) as e:
        print(f"データ処理中にエラーが発生しました: {e}")
        print("受信したデータ:")
        print(json.dumps(データ, indent=2))
        return False, None

def コメント取得(動画ID, window):
    csvファイル名 = f"twitch_コメント_{動画ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        with open(csvファイル名, 'w', newline='', encoding='utf-8') as csvファイル:
            csvライター = csv.writer(csvファイル)
            csvライター.writerow(['整形済みタイムスタンプ', 'タイムスタンプ（秒）', 'ユーザー', 'メッセージ'])

            セッション = requests.Session()
            セッション.headers = {'Client-ID': 'kd1unb4b3q4t58fwlpcbzcbnm76a8fp', 'content-type': 'application/json'}
            レスポンス = セッション.post("https://gql.twitch.tv/gql", JSONデータ取得(動画ID), timeout=10)
            window['OUTPUT'].print("接続成功\n")
            レスポンス.raise_for_status()
            データ = レスポンス.json()
            次ページあり, カーソル = コメント処理(データ, csvライター)

            while 次ページあり and カーソル:
                レスポンス = セッション.post("https://gql.twitch.tv/gql", JSONデータ取得(動画ID, カーソル), timeout=10)
                レスポンス.raise_for_status()
                データ = レスポンス.json()
                次ページあり, カーソル = コメント処理(データ, csvライター)
                if 次ページあり:
                    window['OUTPUT'].print(".", end="")
                    window.refresh()
                    time.sleep(0.1)

        window['OUTPUT'].print(f"\nコメントをCSVファイル '{csvファイル名}' に保存しました。")
        return csvファイル名
    except requests.exceptions.RequestException as e:
        window['OUTPUT'].print(f"リクエスト中にエラーが発生しました: {e}")
    except Exception as e:
        window['OUTPUT'].print(f"予期しないエラーが発生しました: {e}")
    return None

def 秒数から時分秒へ変換(秒数):
    return str(timedelta(seconds=int(秒数))).zfill(8)

def 時分秒から秒数へ変換(時分秒):
    時, 分, 秒 = map(int, 時分秒.split(':'))
    return 時 * 3600 + 分 * 60 + 秒

def 秒数から時分秒へ変換(秒数):
    return str(timedelta(seconds=int(秒数))).zfill(8)

def グラフ描画(df, window):
    debug_print(window, "グラフ描画開始")
    ビンサイズ = 30
    最大秒数 = df['秒数'].max()
    ビン = range(0, 最大秒数 + ビンサイズ, ビンサイズ)

    チャット数 = df.groupby(pd.cut(df['秒数'], bins=ビン)).size()
    非ゼロチャット数 = チャット数[チャット数 != 0]

    棒幅 = 0.5
    棒の数 = len(非ゼロチャット数)
    グラフ幅 = max(19, 棒の数 * 棒幅 * 1.2)  # 1.2は棒と棒の間隔を考慮

    fig, ax = plt.subplots(figsize=(グラフ幅, 6))
    x = np.arange(棒の数) * 棒幅 * 1.2
    バー = ax.bar(x, 非ゼロチャット数.values, width=棒幅)

    for i, バー in enumerate(バー):
        if 非ゼロチャット数.values[i] >= 4:
            バー.set_color('pink')
        else:
            バー.set_color('lightblue')

    ax.set_xlabel('時間')
    ax.set_ylabel('チャット数')
    ax.set_title('30秒ごとのチャット数')

    x目盛り = []
    x目盛りラベル = []
    for i, (区間, カウント) in enumerate(非ゼロチャット数.items()):
        if i % 8 == 0:
            x目盛り.append(x[i])
            時間文字列 = 秒数から時分秒へ変換(区間.left)
            x目盛りラベル.append(時間文字列)

    ax.set_xticks(x目盛り)
    ax.set_xticklabels(x目盛りラベル, rotation=45, ha='right')

    総チャット数 = 非ゼロチャット数.values.sum()
    平均チャット数 = 総チャット数 / len(非ゼロチャット数)
    ax.text(0.02, 0.98, f'総チャット数: {総チャット数}\n30秒あたりの平均チャット数: {平均チャット数:.2f}',
            transform=ax.transAxes, verticalalignment='top')

    plt.tight_layout()
    debug_print(window, "グラフ描画完了")
    return fig

def グラフ更新(window, fig):
    debug_print(window, "グラフ更新開始")
    
    # 既存のグラフキャンバスを削除
    for elem in window['GRAPH'].Widget.winfo_children():
        elem.destroy()
    
    # 新しいグラフキャンバスを作成
    canvas = FigureCanvasTkAgg(fig, master=window['GRAPH'].Widget)
    canvas.draw()
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(side='left', fill='both', expand=1)
    
    # スクロールバーを追加
    scrollbar = sg.Scrollbar(window['GRAPH'].Widget, orientation='horizontal')
    scrollbar.pack(side='bottom', fill='x')
    
    # スクロールバーとキャンバスを連動させる
    scrollbar.config(command=canvas_widget.xview)
    canvas_widget.config(xscrollcommand=scrollbar.set)
    canvas_widget.config(scrollregion=canvas_widget.bbox('all'))
    
    debug_print(window, "グラフ更新完了")

def コメント分析(csvファイル, window):
    debug_print(window, f"CSVファイル '{csvファイル}' の分析を開始")
    df = pd.read_csv(csvファイル)
    df['秒数'] = df['タイムスタンプ（秒）'].astype(int)

    fig = グラフ描画(df, window)
    グラフ更新(window, fig)

    window['OUTPUT'].print("グラフを生成しました。")
    debug_print(window, "コメント分析完了")

def メイン():
    sg.theme('LightBlue2')

    layout = [
        [sg.Text('Twitch動画のURLを入力してね:'), sg.InputText(key='URL')],
        [sg.Button('分析開始'), sg.Button('終了')],
        [sg.Multiline(size=(60, 10), key='OUTPUT', autoscroll=True, reroute_stdout=True, reroute_stderr=True)],
        [sg.Canvas(key='GRAPH')]
    ]

    window = sg.Window('Twitchコメント分析', layout, finalize=True, resizable=True)

    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED or event == '終了':
            break
        if event == '分析開始':
            try:
                動画ID = 動画ID抽出(values['URL'])
                window['OUTPUT'].print(f"動画ID: {動画ID}")
                csvファイル = コメント取得(動画ID, window)
                if csvファイル and os.path.exists(csvファイル):
                    コメント分析(csvファイル, window)
                else:
                    window['OUTPUT'].print("コメントの取得またはCSVファイルの生成に失敗しました。")
            except Exception as e:
                window['OUTPUT'].print(f"エラーが発生しました: {e}")
                window['OUTPUT'].print(traceback.format_exc())

            window['OUTPUT'].print("分析完了")

    window.close()

if __name__ == "__main__":
    メイン()