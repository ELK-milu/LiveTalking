# coding=utf-8
import asyncio
import re

import websockets
import uuid
import json
import gzip
import copy
import os
from datetime import datetime

MESSAGE_TYPES = {11: "audio-only server response", 12: "frontend server response", 15: "error message from server"}
MESSAGE_TYPE_SPECIFIC_FLAGS = {0: "no sequence number", 1: "sequence number > 0",
                               2: "last message from server (seq < 0)", 3: "sequence number < 0"}
MESSAGE_SERIALIZATION_METHODS = {0: "no serialization", 1: "JSON", 15: "custom type"}
MESSAGE_COMPRESSIONS = {0: "no compression", 1: "gzip", 15: "custom compression method"}

# 配置参数
appid = "4487078679"
token = "HvLwi9jvzAOExH7hzbIxEndcZq3C28Dm"
cluster = "volcano_tts"
host = "openspeech.bytedance.com"
api_url = f"wss://{host}/api/v1/tts/ws_binary"

# 默认请求头
default_header = bytearray(b'\x11\x10\x11\x00')

# 输出目录和语音配置
Audio_Name = "小璐_字节跳动"
voice_type = "zh_female_linjianvhai_moon_bigtts"  # 可根据需要修改发音人

# 基础请求模板
request_json = {
    "app": {
        "appid": appid,
        "token": "access_token",
        "cluster": cluster
    },
    "user": {
        "uid": "388808087185088"
    },
    "audio": {
        "voice_type": voice_type,
        "encoding": "mp3",
        "speed_ratio": 1.0,
        "volume_ratio": 1.0,
        "pitch_ratio": 1.0,
    },
    "request": {
        "reqid": "uuid",
        "text": "字节跳动语音合成。",
        "text_type": "plain",
        "operation": "query"
    }
}


class TTSGenerator:
    def __init__(self):
        # 创建输出目录
        if not os.path.exists(Audio_Name):
            os.makedirs(Audio_Name)

    def parse_response(self, res, file):
        protocol_version = res[0] >> 4
        header_size = res[0] & 0x0f
        message_type = res[1] >> 4
        message_type_specific_flags = res[1] & 0x0f
        serialization_method = res[2] >> 4
        message_compression = res[2] & 0x0f

        payload = res[header_size * 4:]

        if message_type == 0xb:  # audio-only server response
            if message_type_specific_flags != 0:  # 有序列号的消息
                sequence_number = int.from_bytes(payload[:4], "big", signed=True)
                payload_size = int.from_bytes(payload[4:8], "big", signed=False)
                payload = payload[8:]
                file.write(payload)
                if sequence_number < 0:  # 最后一条消息
                    return True
            return False
        elif message_type == 0xf:  # 错误消息
            code = int.from_bytes(payload[:4], "big", signed=False)
            msg_size = int.from_bytes(payload[4:8], "big", signed=False)
            error_msg = payload[8:]
            if message_compression == 1:
                error_msg = gzip.decompress(error_msg)
            error_msg = str(error_msg, "utf-8")
            print(f"错误: {error_msg}")
            return True
        return False

    def sanitize_filename(self, filename):
        # 替换Windows文件名中不允许的字符
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        # 移除连续的点和空格
        filename = re.sub(r'\.{2,}', ".", filename)
        filename = re.sub(r' {2,}', " ", filename)
        # 移除开头和结尾的空格和点
        filename = filename.strip(". ")
        return filename

    async def generate_tts(self, emotion, text):
        # 生成安全的文件名（只移除英文句点）
        safe_text = self.sanitize_filename(text)
        filename = f"{emotion}_{safe_text}.mp3"
        filename = filename[:200] + ".mp3" if len(filename) > 200 else filename
        filepath = os.path.join(Audio_Name, filename)

        # 创建请求
        submit_request_json = copy.deepcopy(request_json)
        submit_request_json["audio"]["voice_type"] = voice_type
        submit_request_json["request"]["reqid"] = str(uuid.uuid4())
        submit_request_json["request"]["operation"] = "submit"
        submit_request_json["request"]["text"] = text

        # 准备请求数据
        payload_bytes = str.encode(json.dumps(submit_request_json))
        payload_bytes = gzip.compress(payload_bytes)
        full_client_request = bytearray(default_header)
        full_client_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        full_client_request.extend(payload_bytes)

        # 发送请求并接收响应
        header = {"Authorization": f"Bearer; {token}"}
        async with websockets.connect(api_url, additional_headers=header, ping_interval=None) as ws:
            await ws.send(full_client_request)
            with open(filepath, "wb") as file_to_save:
                while True:
                    res = await ws.recv()
                    done = self.parse_response(res, file_to_save)
                    if done:
                        break
            print(f"合成完成: {emotion} - {text[:30]}...")


async def main():
    # 读取samples.json文件
    with open('samples.json', 'r', encoding='utf-8') as f:
        samples = json.load(f)

    # 初始化TTS生成器
    tts_generator = TTSGenerator()

    await tts_generator.generate_tts("中立",
                                     "第137届广交会二期展会目前正在广州举行。与一期的情况一样，风雨无阻故人来，全球客商正穿过国际贸易的风浪、穿过风雨，共赴这场全球规模最大的贸易展会之约。在广交会现场，全球客商并没有感受到中国企业因关税冲击带来信心减弱，反而感受到扑面而来的热情。中国的外贸企业正借助广交会，依靠高质量产品、自有优势，全力突围、开拓新市场。")

    print("\n所有语音文件生成完成！")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())