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
import tkinter as tk

warnings.simplefilter(action='ignore', category=FutureWarning)

# Scrollable Canvas for Graphs (Problem 1)
def draw_figure(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg

def 動画ID抽出(url):
    マッチ = re.search(r'videos/(\d+)', url)
    if マッチ:
        return マッチ.group(1)
    else:
        raise ValueError("無効なTwitch URLです。有効な動画URLを入力してください。")

def JSONデータ取得(動画ID, カーソル=None):
    query = {
        "operationName": "VideoCommentsByOffsetOrCursor",
        "variables": {
            "videoID": 動画ID,
            "contentOffsetSeconds": 0 if カーソル is None else None,
            "cursor": カーソル if カーソル else None
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
            }
        }
    }
    return json.dumps([query])

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

            while 次ページあり:
                time.sleep(2)
                レスポンス = セッション.post("https://gql.twitch.tv/gql", JSONデータ取得(動画ID, カーソル), timeout=10)
                データ = レスポンス.json()
                次ページあり, カーソル = コメント処理(データ, csvライター)
                
            window['OUTPUT'].print(f"コメント取得が完了しました。ファイル名: {csvファイル名}\n")
    except Exception as e:
        window['OUTPUT'].print(f"エラーが発生しました: {str(e)}\n")

# GUI Layout with Scrollable Graphs
layout = [
    [sg.Text('Twitch Video URL:'), sg.Input(key='VIDEO_URL'), sg.Button('Fetch Comments')],
    [sg.Text('Output:'), sg.Output(size=(100, 20), key='OUTPUT')],
    [sg.Canvas(key='CANVAS', size=(800, 600))],  # Canvas for scrollable graph
]

window = sg.Window('Twitch Comment Analyzer', layout, finalize=True)
canvas_elem = window['CANVAS'].TKCanvas

while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
        break
    if event == 'Fetch Comments':
        try:
            動画ID = 動画ID抽出(values['VIDEO_URL'])
            コメント取得(動画ID, window)
        except Exception as e:
            window['OUTPUT'].print(f"Error: {str(e)}")

window.close()