"""
Voice Messenger Relay Server
Simple WebSocket relay for voice messages between devices over the Internet
No data storage - just forwards messages between connected devices
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict

try:
    from aiohttp import web
    import aiohttp
except ImportError:
    print("Installing aiohttp...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'aiohttp'])
    from aiohttp import web
    import aiohttp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

connected_devices: Dict[str, web.WebSocketResponse] = {}
device_info: Dict[str, dict] = {}

async def handle_websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    device_id = None
    logger.info("New WebSocket connection")
    
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')
                    
                    if msg_type == 'register':
                        device_id = await handle_register(ws, data)
                    elif msg_type == 'voice_message':
                        await handle_voice_message(data, device_id)
                    elif msg_type == 'message_heard':
                        await handle_message_heard(data, device_id)
                    elif msg_type == 'ping':
                        await ws.send_json({'type': 'pong'})
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f'WebSocket error: {ws.exception()}')
    finally:
        if device_id and device_id in connected_devices:
            del connected_devices[device_id]
            logger.info(f"Device {device_id} disconnected ({len(connected_devices)} devices online)")
    
    return ws

async def handle_register(ws: web.WebSocketResponse, data: dict) -> str:
    device_id = data.get('device_id')
    device_name = data.get('device_name', 'Unknown')
    friends = data.get('friends', [])
    
    if not device_id:
        await ws.send_json({'type': 'error', 'message': 'device_id required'})
        return None
    
    connected_devices[device_id] = ws
    device_info[device_id] = {'name': device_name, 'friends': friends, 'last_seen': datetime.now().isoformat()}
    logger.info(f"Device registered: {device_name} ({device_id}) - {len(connected_devices)} devices online")
    
    await ws.send_json({'type': 'registered', 'device_id': device_id, 'server_time': datetime.now().isoformat()})
    
    online_friends = [fid for fid in friends if fid in connected_devices]
    if online_friends:
        await ws.send_json({'type': 'friends_online', 'friends': online_friends})
    
    return device_id

async def handle_voice_message(data: dict, sender_id: str):
    try:
        recipient_id = data.get('recipient_id')
        message_id = data.get('message_id')
        audio_data = data.get('audio_data')
        timestamp = data.get('timestamp')
        
        if not recipient_id or not message_id or not audio_data:
            logger.warning("Invalid voice message format")
            return
        
        if recipient_id not in connected_devices:
            logger.warning(f"Recipient {recipient_id} not online")
            sender_ws = connected_devices.get(sender_id)
            if sender_ws:
                await sender_ws.send_json({'type': 'recipient_offline', 'recipient_id': recipient_id, 'message_id': message_id})
            return
        
        recipient_ws = connected_devices[recipient_id]
        await recipient_ws.send_json({'type': 'voice_message', 'sender_id': sender_id, 'message_id': message_id, 'audio_data': audio_data, 'timestamp': timestamp})
        logger.info(f"Voice message forwarded: {sender_id} -> {recipient_id} ({len(audio_data)} bytes)")
        
        sender_ws = connected_devices.get(sender_id)
        if sender_ws:
            await sender_ws.send_json({'type': 'message_delivered', 'recipient_id': recipient_id, 'message_id': message_id})
    except Exception as e:
        logger.error(f"Error forwarding voice message: {e}")

async def handle_message_heard(data: dict, listener_id: str):
    try:
        sender_id = data.get('sender_id')
        message_id = data.get('message_id')
        
        if not sender_id or not message_id:
            logger.warning("Invalid message_heard format")
            return
        
        if sender_id not in connected_devices:
            logger.warning(f"Sender {sender_id} not online for heard notification")
            return
        
        sender_ws = connected_devices[sender_id]
        await sender_ws.send_json({'type': 'message_heard', 'listener_id': listener_id, 'message_id': message_id})
        logger.info(f"Message heard notification: {message_id} ({listener_id} -> {sender_id})")
    except Exception as e:
        logger.error(f"Error handling message_heard: {e}")

async def handle_status(request):
    return web.json_response({'status': 'ok', 'connected_devices': len(connected_devices), 'uptime': 'running', 'timestamp': datetime.now().isoformat()})

async def handle_root(request):
    html = """<!DOCTYPE html>
<html><head><title>Voice Messenger Relay</title>
<style>body{font-family:Arial,sans-serif;max-width:800px;margin:50px auto;padding:20px;background:#f5f5f5}
.container{background:white;padding:30px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
h1{color:#2196F3}.status{background:#e3f2fd;padding:15px;border-radius:5px;margin:20px 0}
code{background:#f5f5f5;padding:2px 6px;border-radius:3px}</style></head>
<body><div class="container"><h1>🎙️ Voice Messenger Relay Server</h1>
<div class="status"><strong>Status:</strong> ✅ Running<br>
<strong>Connected Devices:</strong> <span id="devices">""" + str(len(connected_devices)) + """</span><br>
<strong>Protocol:</strong> WebSocket</div>
<h2>📡 Connection Info</h2><p>WebSocket URL: <code>ws://""" + request.host + """/ws</code></p>
<p>Status API: <code>""" + str(request.url) + """status</code></p>
<h2>📝 Features</h2><ul><li>Real-time message relay between devices</li>
<li>No message storage - instant forwarding only</li><li>Device online/offline detection</li>
<li>Message delivery confirmations</li></ul>
<h2>🔒 Privacy</h2><p>This server does not store any messages or audio data. All voice messages are forwarded directly between devices in real-time.</p></div>
<script>setInterval(async()=>{const res=await fetch('/status');const data=await res.json();
document.getElementById('devices').textContent=data.connected_devices;},5000);</script></body></html>"""
    return web.Response(text=html, content_type='text/html')

async def cleanup_stale_devices(app):
    while True:
        await asyncio.sleep(300)
        disconnected = [dev_id for dev_id in device_info.keys() if dev_id not in connected_devices]
        for dev_id in disconnected:
            del device_info[dev_id]
        if disconnected:
            logger.info(f"Cleaned up {len(disconnected)} stale device entries")

async def start_background_tasks(app):
    app['cleanup_task'] = asyncio.create_task(cleanup_stale_devices(app))

async def cleanup_background_tasks(app):
    app['cleanup_task'].cancel()
    await app['cleanup_task']

def create_app():
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/status', handle_status)
    app.router.add_get('/ws', handle_websocket)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Voice Messenger Relay Server on port {port}")
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=port)
