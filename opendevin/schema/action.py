from pydantic import BaseModel, Field


class ActionType(BaseModel):
    INIT: str = Field(default="initialize")
    """Initialize the agent. Only sent by client.
    """

    START: str = Field(default="start")
    """Starts a new development task. Only sent by the client.
    """

    READ: str = Field(default="read")
    """Reads the content of a file.
    """

    WRITE: str = Field(default="write")
    """Writes the content to a file.
    """

    RUN: str = Field(default="run")
    """Runs a command.
    """

    KILL: str = Field(default="kill")
    """Kills a background command.
    """

    BROWSE: str = Field(default="browse")
    """Opens a web page.
    """

    RECALL: str = Field(default="recall")
    """Searches long-term memory
    """

    THINK: str = Field(default="think")
    """Allows the agent to make a plan, set a goal, or record thoughts
    """

    FINISH: str = Field(default="finish")
    """If you"re absolutely certain that you"ve completed your task and have tested your work, 
    use the finish action to stop working.
    """

    CHAT: str = Field(default="chat")

    SUMMARIZE: str = Field(default="summarize")

    ADD_TASK: str = Field(default="add_task")

    MODIFY_TASK: str = Field(default="modify_task")

    NULL: str = Field(default="null")
