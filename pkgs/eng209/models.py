import ipywidgets as widgets
from collections.abc import Callable
from enum import Enum


class QuizType(Enum):
    INVALID = 0
    SINGLE_CHOICE = 1
    MULTI_CHOICE = 2


class Context:
    def __init__(self, json: dict):
        self.__source: str | None = json.get("source")
        self.__group: int | None = json.get("group")
        self.__uuid: str | None = json.get("uuid")
        self.__label: str | None = json.get("label")

    @property
    def source(self) -> str | None:
        return self.__source

    @property
    def group(self) -> int | None:
        return self.__group

    @property
    def uuid(self) -> str | None:
        return self.__uuid

    @property
    def label(self) -> str | None:
        return self.__label


class Quiz:
    def __init__(self, json: dict, context: Context, defaults: dict = {}):
        self.__label: str | None = json.get("label")
        self.__groups: list[int] = json.get("groups", [])
        self.__question: str | None = json.get("question")
        self.__options: list[str] | dict[str, bool] | None = json.get("options")
        self.__answer: int = json.get("answer", -1)
        self.__uuid: str | None = json.get("uuid")
        self.__context: Context = context
        self.__container: widgets.Box | None = Container(
            json.get("container")
        ) or defaults.get("container")

        if not self.__question or not self.__options:
            self.__type: QuizType = QuizType.INVALID
        elif isinstance(self.__options, dict):
            self.__type = QuizType.MULTI_CHOICE
        elif (
            isinstance(self.__options, list)
            and self.__answer >= 0
            and self.__answer < len(self.__options)
        ):
            self.__type = QuizType.SINGLE_CHOICE
        else:
            self.__type = QuizType.INVALID

    @property
    def context(self) -> Context:
        return self.__context

    @property
    def type(self) -> QuizType:
        return self.__type

    @property
    def question(self) -> str | None:
        return self.__question

    @property
    def answer(self) -> int | None:
        return self.__answer

    @property
    def option_list(self) -> list[str]:
        if isinstance(self.__options, list):
            return self.__options
        else:
            return []

    @property
    def option_map(self) -> dict[str, bool]:
        if isinstance(self.__options, list):
            return {
                k: v
                for k, v in zip(
                    self.__options,
                    [i == self.__answer for i in range(0, len(self.__options))],
                )
            }
        elif isinstance(self.__options, dict):
            return self.__options
        else:
            return {}

    @property
    def uuid(self) -> str | None:
        return self.__uuid

    @property
    def groups(self) -> list[int]:
        return self.__groups

    @property
    def label(self) -> str | None:
        return self.__label

    @property
    def container(self) -> widgets.Box | None:
        return self.__container


def Accordion() -> widgets.VBox:
    return widgets.Accordion()


def Vertical() -> None:
    # 'None' stacks the widgets vertically (this is the default).
    return None


def Container(name: str | None) -> Callable[[], widgets.Box | None] | None:
    if not name:
        return None
    elif name.lower() == "accordion":
        return Accordion
    else:
        return Vertical


__all__ = ["Accordion", "Container", "Context", "Quiz", "QuizType", "Vertical"]
