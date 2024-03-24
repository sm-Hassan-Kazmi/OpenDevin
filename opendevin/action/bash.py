from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base import Action, Executable

if TYPE_CHECKING:
    from opendevin.controller import AgentController


@dataclass
class CmdRunAction(Action, Executable):
    command: str
    background: bool = False

    def run(self, controller: "AgentController") -> str:
        return controller.command_manager.run_command(self.command, self.background)


@dataclass
class CmdKillAction(Action, Executable):
    id: int

    def run(self, controller: "AgentController") -> str:
        return controller.command_manager.kill_command(self.id)
