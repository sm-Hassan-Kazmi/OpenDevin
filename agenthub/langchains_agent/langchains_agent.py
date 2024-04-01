from typing import List
from opendevin.agent import Agent
from opendevin.state import State
from opendevin.action import Action
from opendevin.llm.llm import LLM
from opendevin.schema import ActionType
import agenthub.langchains_agent.utils.prompts as prompts
from agenthub.langchains_agent.utils.monologue import Monologue
from agenthub.langchains_agent.utils.memory import LongTermMemory

MAX_MONOLOGUE_LENGTH = 20000
MAX_OUTPUT_LENGTH = 5000

INITIAL_THOUGHTS = [
    "I exist!",
    "Hmm...looks like I can type in a command line prompt",
    "Looks like I have a web browser too!",
    "Here's what I want to do: $TASK",
    "How am I going to get there though?",
    "It seems like I have some kind of short term memory.",
    "Each of my thoughts seems to be stored in a JSON array.",
    "It seems whatever I say next will be added as an object to the list.",
    "But no one has perfect short-term memory. My list of thoughts will be summarized and condensed over time, losing information in the process.",
    "Fortunately I have long term memory!",
    "I can just perform a recall action, followed by the thing I want to remember. And then related thoughts just spill out!",
    "Sometimes they're random thoughts that don't really have to do with what I wanted to remember. But usually they're exactly what I need!",
    "Let's try it out!",
    "RECALL what it is I want to do",
    "Here's what I want to do: $TASK",
    "How am I going to get there though?",
    "Neat! And it looks like it's easy for me to use the command line too! I just have to perform a run action and include the command I want to run in the command argument. The command output just jumps into my head!",
    'RUN echo "hello world"',
    "hello world",
    "Cool! I bet I can write files too using the write action.",
    "WRITE echo \"console.log('hello world')\" > test.js",
    "",
    "I just created test.js. I'll try and run it now.",
    "RUN node test.js",
    "hello world",
    "It works!",
    "I'm going to try reading it now using the read action.",
    "READ test.js",
    "console.log('hello world')",
    "Nice! I can read files too!",
    "And if I want to use the browser, I just need to use the browse action and include the url I want to visit in the url argument",
    "Let's try that...",
    "BROWSE google.com",
    '<form><input type="text"></input><button type="submit"></button></form>',
    "I can browse the web too!",
    "And once I have completed my task, I can use the finish action to stop working.",
    "But I should only use the finish action when I'm absolutely certain that I've completed my task and have tested my work.",
    "Very cool. Now to accomplish my task.",
    "I'll need a strategy. And as I make progress, I'll need to keep refining that strategy. I'll need to set goals, and break them into sub-goals.",
    "In between actions, I must always take some time to think, strategize, and set new goals. I should never take two actions in a row.",
    "OK so my task is to $TASK. I haven't made any progress yet. Where should I start?",
    "It seems like there might be an existing project here. I should probably start by running `ls` to see what's here.",
]


class LangchainsAgent(Agent):
    _initialized = False

    def __init__(self, llm: LLM):
        super().__init__(llm)
        self.monologue = Monologue()
        self.memory = LongTermMemory()

    def _add_event(self, event: dict):
        if (
            "args" in event
            and "output" in event["args"]
            and len(event["args"]["output"]) > MAX_OUTPUT_LENGTH
        ):
            event["args"]["output"] = (
                event["args"]["output"][:MAX_OUTPUT_LENGTH] + "..."
            )

        self.monologue.add_event(event)
        self.memory.add_event(event)
        if self.monologue.get_total_length() > MAX_MONOLOGUE_LENGTH:
            self.monologue.condense(self.llm)

    def _initialize(self, task):
        if self._initialized:
            return

        if task is None or task == "":
            raise ValueError("Instruction must be provided")
        self.monologue = Monologue()
        self.memory = LongTermMemory()

        next_is_output = False
        for thought in INITIAL_THOUGHTS:
            thought = thought.replace("$TASK", task)
            if next_is_output:
                d = {"action": "output", "args": {"output": thought}}
                next_is_output = False
            else:
                if thought.startswith("RUN"):
                    command = thought.split("RUN ")[1]
                    d = {"action": ActionType.RUN, "args": {"command": command}}
                    next_is_output = True
                elif thought.startswith("WRITE"):
                    parts = thought.split("WRITE ")[1].split(" > ")
                    path = parts[1]
                    content = parts[0]
                    d = {
                        "action": ActionType.WRITE,
                        "args": {"file": path, "content": content},
                    }
                    next_is_output = True
                elif thought.startswith("READ"):
                    path = thought.split("READ ")[1]
                    d = {"action": ActionType.READ, "args": {"file": path}}
                    next_is_output = True
                elif thought.startswith("RECALL"):
                    query = thought.split("RECALL ")[1]
                    d = {"action": ActionType.RECALL, "args": {"query": query}}
                    next_is_output = True

                elif thought.startswith("BROWSE"):
                    url = thought.split("BROWSE ")[1]
                    d = {"action": ActionType.BROWSE, "args": {"url": url}}
                    next_is_output = True
                else:
                    d = {"action": ActionType.THINK, "args": {"thought": thought}}

            self._add_event(d)
        self._initialized = True

    def step(self, state: State) -> Action:
        self._initialize(state.plan.main_goal)
        for prev_action, obs in state.updated_info:
            self._add_event(prev_action.to_dict())
            self._add_event(obs.to_dict())

        state.updated_info = []

        prompt = prompts.get_request_action_prompt(
            state.plan.main_goal,
            self.monologue.get_thoughts(),
            state.background_commands_obs,
        )
        messages = [{"content": prompt, "role": "user"}]
        resp = self.llm.completion(messages=messages)
        action_resp = resp["choices"][0]["message"]["content"]
        action = prompts.parse_action_response(action_resp)
        self.latest_action = action
        return action

    def search_memory(self, query: str) -> List[str]:
        return self.memory.search(query)
