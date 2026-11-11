import random
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

        self.tokens: Dict[str, dict] = {
            "token-1": {
                "x": 100, "y": 100, "name": "Игрок",
                "color": "#e74c3c", "image_url": None, "scale": 1.0
            }
        }

        self.current_map = None
        self.clues = []
        self.map_scale = 1.0
        self.camera_state = {"x": 0, "y": 0, "rotation": 0}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

        init_data = {
            "type": "init",
            "tokens": self.tokens,
            "map_url": self.current_map,
            "clues": self.clues,
            "map_scale": self.map_scale,
            "camera": self.camera_state
        }
        await websocket.send_text(json.dumps(init_data))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass


manager = ConnectionManager()


def roll_dice(sides: int, count: int = 1, modifier: int = 0):
    if count > 100:
        return "Слишком много кубиков!"
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    result_text = f"🎲 Бросок {count}d{sides}: [{', '.join(map(str, rolls))}]"
    if modifier != 0:
        result_text += f" {'+' if modifier > 0 else ''}{modifier}"
    result_text += f" = **{total}**"
    return result_text


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                parsed_data = json.loads(data)
                msg_type = parsed_data.get("type")

                if msg_type == "roll":
                    sides = parsed_data.get("sides", 20)
                    count = parsed_data.get("count", 1)
                    result = roll_dice(sides, count)
                    await manager.broadcast(json.dumps({
                        "type": "chat",
                        "text": result,
                        "is_system": True
                    }))
                    continue

                elif msg_type == "move":
                    token_id = parsed_data.get("id")
                    if token_id in manager.tokens:
                        manager.tokens[token_id]["x"] = parsed_data.get("x")
                        manager.tokens[token_id]["y"] = parsed_data.get("y")
                        await manager.broadcast(data)
                    continue

                elif msg_type == "create_token":
                    token_id = f"token-{random.randint(1000, 9999)}"
                    manager.tokens[token_id] = {
                        "x": 200, "y": 200, "name": "Новый герой",
                        "color": "#e74c3c", "image_url": None, "scale": 1.0
                    }
                    await manager.broadcast(json.dumps({
                        "type": "token_created",
                        "id": token_id,
                        "token": manager.tokens[token_id]
                    }))
                    continue

                elif msg_type == "update_token":
                    token_id = parsed_data.get("id")
                    if token_id in manager.tokens:
                        if "name" in parsed_data:
                            manager.tokens[token_id]["name"] = parsed_data["name"]
                        if "color" in parsed_data:
                            manager.tokens[token_id]["color"] = parsed_data["color"]
                        if "image_url" in parsed_data:
                            manager.tokens[token_id]["image_url"] = parsed_data["image_url"]
                        if "scale" in parsed_data:
                            manager.tokens[token_id]["scale"] = parsed_data["scale"]

                        await manager.broadcast(data)
                    continue

                elif msg_type == "delete_token":
                    token_id = parsed_data.get("id")
                    if token_id in manager.tokens:
                        del manager.tokens[token_id]
                        await manager.broadcast(data)
                    continue

                elif msg_type == "camera_move":
                    manager.camera_state["x"] = parsed_data.get("x", 0)
                    manager.camera_state["y"] = parsed_data.get("y", 0)
                    manager.camera_state["rotation"] = parsed_data.get("rotation", 0)
                    await manager.broadcast(data)
                    continue

                elif msg_type == "map_change":
                    manager.current_map = parsed_data.get("url")
                    await manager.broadcast(data)
                    continue

                elif msg_type == "map_scale":
                    manager.map_scale = parsed_data.get("scale", 1.0)
                    await manager.broadcast(data)
                    continue

                elif msg_type == "chat":
                    await manager.broadcast(data)
                    continue

                elif msg_type == "chat_image":
                    await manager.broadcast(data)
                    continue

                elif msg_type == "add_clue":
                    clue_url = parsed_data.get("url")
                    if clue_url and clue_url not in manager.clues:
                        manager.clues.append(clue_url)
                        await manager.broadcast(data)
                    continue

                elif msg_type == "remove_clue":
                    clue_url = parsed_data.get("url")
                    if clue_url in manager.clues:
                        manager.clues.remove(clue_url)
                        await manager.broadcast(data)
                    continue

                elif msg_type == "draw":
                    await manager.broadcast(data)
                    continue

                elif msg_type == "clear_canvas":
                    await manager.broadcast(data)
                    continue

            except Exception as e:
                print("Ошибка обработки сообщения:", e)

    except WebSocketDisconnect:
        manager.disconnect(websocket)