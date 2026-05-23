"""Holle Music — Textual TUI 主应用."""

from dataclasses import dataclass
from enum import Enum, auto


class CommandType(Enum):
    NONE = auto()
    PLAY = auto()
    PAUSE = auto()
    STOP = auto()
    NEXT = auto()
    PREVIOUS = auto()
    VOLUME = auto()
    SCAN = auto()
    PLAYLIST = auto()
    HELP = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    type: CommandType
    args: str = ""


COMMAND_MAP: dict[str, CommandType] = {
    "play": CommandType.PLAY,
    "pause": CommandType.PAUSE,
    "stop": CommandType.STOP,
    "resume": CommandType.PLAY,  # resume is equivalent to play
    "next": CommandType.NEXT,
    "prev": CommandType.PREVIOUS,
    "previous": CommandType.PREVIOUS,
    "volume": CommandType.VOLUME,
    "vol": CommandType.VOLUME,
    "scan": CommandType.SCAN,
    "playlist": CommandType.PLAYLIST,
    "help": CommandType.HELP,
    "?": CommandType.HELP,
    "quit": CommandType.QUIT,
    "exit": CommandType.QUIT,
    "q": CommandType.QUIT,
}


def parse_command(text: str) -> Command:
    """解析用户输入的命令字符串."""
    text = text.strip()
    if not text:
        return Command(CommandType.NONE)

    parts = text.split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    cmd_type = COMMAND_MAP.get(keyword, CommandType.UNKNOWN)
    return Command(cmd_type, args)


def main() -> None:
    """程序入口 — 占位."""
    print("Holle Music — 即将实现")
