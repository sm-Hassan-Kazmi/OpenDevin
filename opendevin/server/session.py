import asyncio
import os
from typing import Optional

from fastapi import WebSocketDisconnect

from opendevin import config
from opendevin.action import Action, NullAction
from opendevin.agent import Agent
from opendevin.controller import AgentController
from opendevin.llm.llm import LLM
from opendevin.observation import Observation, NullObservation, UserMessageObservation

DEFAULT_API_KEY = config.get_or_none("LLM_API_KEY")
DEFAULT_BASE_URL = config.get_or_none("LLM_BASE_URL")
DEFAULT_WORKSPACE_DIR = config.get_or_default("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
LLM_MODEL = config.get_or_default("LLM_MODEL", "gpt-4-0125-preview")
CONTAINER_IMAGE = config.get_or_default("SANDBOX_CONTAINER_IMAGE", "ghcr.io/opendevin/sandbox")

class Session:
    def __init__(self, websocket):
        self.websocket = websocket
        self.controller: Optional[AgentController] = None
        self.agent: Optional[Agent] = None
        self.agent_task: Optional[asyncio.Task] = None
        asyncio.create_task(self.create_controller(), name="create_controller")

    async def send_error(self, message: str):
        if self.websocket:
            try:
                await self.websocket.send_json({"error": True, "message": message})
            except Exception as e:
                print(f"Error sending error message to client: {e}")

    async def send_message(self, message: str):
        if self.websocket:
            try:
                await self.websocket.send_json({"message": message})
            except Exception as e:
                print(f"Error sending message to client: {e}")

    async def start_listening(self):
        try:
            while True:
                try:
                    data = await self.websocket.receive_json()
                except ValueError:
                    await self.send_error("Invalid JSON")
                    continue

                action = data.get("action", None)
                if action is None:
                    await self.send_error("Invalid event")
                    continue
                if action == "initialize":
                    await self.create_controller(data)
                elif action == "start":
                    await self.start_task(data)
                else:
                    if self.controller is None:
                        await self.send_error("No agent started. Please wait a second...")
                    elif action == "chat":
                        self.controller.add_history(NullAction(), UserMessageObservation(data["message"]))
                    else:
                        await self.send_error("Unsupported action")

        except WebSocketDisconnect:
            print("Client websocket disconnected")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    async def create_controller(self, start_event=None):
        directory = DEFAULT_WORKSPACE_DIR
        if start_event and "directory" in start_event["args"]:
            directory = start_event["args"]["directory"]
        agent_cls = "LangchainsAgent"
        if start_event and "agent_cls" in start_event["args"]:
            agent_cls = start_event["args"]["agent_cls"]
        model = LLM_MODEL
        if start_event and "model" in start_event["args"]:
            model = start_event["args"]["model"]
        api_key = DEFAULT_API_KEY
        if start_event and "api_key" in start_event["args"]:
            api_key = start_event["args"]["api_key"]
        api_base = DEFAULT_BASE_URL
        if start_event and "api_base" in start_event["args"]:
            api_base = start_event["args"]["api_base"]
        container_image = CONTAINER_IMAGE
        if start_event and "container_image" in start_event["args"]:
            container_image = start_event["args"]["container_image"]
        if not os.path.exists(directory):
            print(f"Workspace directory {directory} does not exist. Creating it...")
            os.makedirs(directory)
        directory = os.path.relpath(directory, os.getcwd())
        llm = LLM(model=model, api_key=api_key, base_url=api_base)
        AgentCls = Agent.get_cls(agent_cls)
        self.agent = AgentCls(llm)
        try:
            self.controller = AgentController(self.agent, workdir=directory, container_image=container_image, callbacks=[self.on_agent_event])
        except Exception as e:
            print(f"Error creating controller: {e}")
            await self.send_error("Error creating controller. Please check Docker is running using `docker ps`.")
            return
        await self.send_message("Control loop started.")

    async def start_task(self, start_event):
        if "task" not in start_event["args"]:
            await self.send_error("No task specified")
            return
        await self.send_message("Starting new task...")
        task = start_event["args"]["task"]
        if self.controller is None:
            await self.send_error("No agent started. Please wait a second...")
            return
        self.agent_task = asyncio.create_task(self.controller.start_loop(task), name="agent_loop")

    def on_agent_event(self, event: Observation | Action):
        if not isinstance(event, (NullAction, NullObservation)):
            event_dict = event.to_dict()
            asyncio.create_task(self.send(event_dict), name="send_event_in_callback")
