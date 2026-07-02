import os
import re
import sys
import streamlit as st
from yt_dlp import YoutubeDL

# ページの設定
st.set_page_config(page_title="youtube→mp3", page_icon="🎵", layout="centered")

# ==========================================
# 1. ロジック部分（数値の秒数を直接受け取る形に洗練）
# ==========================================
def validate_url(url: str) -> bool:
    if not url or not url.strip():
        return False
    if not re.match(r'^https?://', url):
        return False
    return True

def format_seconds_to_time(seconds: float) -> str:
    """秒数を '分:秒' の形式に変換して見やすくする"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"

@st.cache_data(show_spinner=False)
def fetch_video_info(url: str) -> dict:
    """動画情報を取得（キャッシュ対応）"""
    ydl_opts = {'extract_flat': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'Unknown Title'),
            'duration': info.get('duration', 0)
        }

def download_trim_and_normalize(url: str, start_sec: float, end_sec: float, output_dir: str = "downloads") -> str:
    """
    スライダーから受け取った秒数（数値）を元に、
    切り出し・音量均一化を行ってMP3を生成します。
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # FFmpegの引数設定（数値をそのまま文字列にして渡す）
    ffmpeg_input_args = ['-ss', str(start_sec), '-to', str(end_sec)]
    ffmpeg_output_args = ['-filter:a', 'loudnorm=I=-16:TP=-1.5:LRA=11']

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'external_downloader_args': {'ffmpeg_i': ffmpeg_input_args},
        'postprocessor_args': {'ffmpeg': ffmpeg_output_args},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)
        mp3_filename = os.path.splitext(filename)[0] + ".mp3"
        return mp3_filename

# ==========================================
# 2. フロントエンド部分 (Streamlit UI)
# ==========================================
st.title("🎵 youtube → mp3 変換アプリ")
st.write("動画のURLから音声を抽出し、トリミングと音量均一化を行ってMP3でダウンロードします。")

# セッション状態の初期化
if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "last_url" not in st.session_state:
    st.session_state.last_url = ""

# URL入力
url_input = st.text_input("動画のURLを入力してください:", placeholder="https://www.youtube.com/watch?v=...")

if url_input != st.session_state.last_url:
    st.session_state.video_info = None
    st.session_state.last_url = url_input

# 動画情報の読み込み
if url_input and validate_url(url_input):
    if st.button("動画情報を読み込む 🔍") or st.session_state.video_info is not None:
        if st.session_state.video_info is None:
            with st.spinner("動画の情報を取得中..."):
                try:
                    st.session_state.video_info = fetch_video_info(url_input)
                except Exception as e:
                    st.error(f"動画情報の取得に失敗しました。URLを確認してください。")
        
        if st.session_state.video_info:
            info = st.session_state.video_info
            st.info(f"**タイトル:** {info['title']}\n\n**全体の長さ:** {format_seconds_to_time(info['duration'])}")
            
            st.subheader("✂️ トリミング＆変換設定")
            st.write("スライダーを動かして、抽出したい音声の範囲（開始位置と終了位置）を指定してください。")
            
            # 【新機能】レンジスライダーの設置
            # min_valueからmax_valueの間で、初期値(value)を(0秒, 動画の末尾秒)に設定
            max_duration = float(info['duration'])
            
            # 動画が0秒（ライブ配信などで取得できない場合）の安全策
            if max_duration <= 0:
                st.error("動画の長さを正しく取得できませんでした。トリミング機能は利用できません。")
            else:
                # ユーザーが直感的に動かせるツマミ
                time_range = st.slider(
                    "切り出し範囲（秒単位）",
                    min_value=0.0,
                    max_value=max_duration,
                    value=(0.0, max_duration),
                    step=1.0
                )
                
                # 選択された秒数を「分:秒」に変換して分かりやすく画面に表示
                start_sec, end_sec = time_range
                st.write(f"🎵 **選択中の範囲:** `{format_seconds_to_time(start_sec)}` ～ `{format_seconds_to_time(end_sec)}` "
                         f"(合計時間: {int(end_sec - start_sec)}秒)")
                
                # 変換実行ボタン
                if st.button("MP3に変換する 🚀", type="primary"):
                    with st.spinner("音声抽出・音量均一化の処理中..."):
                        try:
                            # 文字列パースを介さず、数値をそのままロジックに渡す
                            mp3_path = download_trim_and_normalize(url_input, start_sec, end_sec)
                            
                            if os.path.exists(mp3_path):
                                st.success("🎉 変換が完了しました！")
                                with open(mp3_path, "rb") as f:
                                    st.download_button(
                                        label="📥 MP3ファイルをダウンロード",
                                        data=f,
                                        file_name=os.path.basename(mp3_path),
                                        mime="audio/mp3"
                                )
                            else:
                                st.error("ファイルが見てつかりません。")
                        except Exception as e:
                            st.error(f"処理中にエラーが発生しました: {e}")
else:
    if url_input:
        st.warning("有効なURLの形式（http:// または https://）で入力してください。")