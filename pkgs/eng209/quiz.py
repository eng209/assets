import ipywidgets as widgets
import json
import urllib.request
from urllib.parse import urlparse
from IPython.display import display, clear_output
from json import JSONDecodeError
from collections.abc import Callable
from enum import Enum

from .models import *
from . import get_project_root, _marker
from . import db


def create_quiz_pickone(quiz: Quiz):
    """
    Displays a quiz where one option can be selected.
    """
    radio = widgets.RadioButtons(
        options=quiz.option_list,
        layout=widgets.Layout(width="auto"),
        style={"description_width": "initial"},
    )

    button = widgets.Button(description="Valider", button_style="success")
    output = widgets.Output()

    def check(b):
        with output:
            output.clear_output()
            if radio.value is None:
                print("⚠️ Choisissez une option SVP.")
            elif radio.value == quiz.option_list[quiz.answer]:
                score = 1.0
                print("✅ Correct!")
            else:
                score = 0.0
                print("❌ Réessaie!")
            db.insert_score(quiz, score)

    button._click_handlers.callbacks.clear()
    button.on_click(check)

    if quiz.container:
        container = quiz.container()
    else:
        container = None

    if container:
        content = widgets.VBox(
            [
                radio,
                button,
                output,
            ]
        )
        container.children = [content]
        container.set_title(0, quiz.question)
        display(container)
    else:
        content = widgets.VBox(
            [
                widgets.HTML(f"<b>{quiz.question}</b>"),
                radio,
                button,
                output,
            ]
        )
        display(content)


def create_quiz_select_all_that_apply(quiz: Quiz):
    """
    Displays a quiz where multiple options can be selected.
    """
    checkboxes = [
        widgets.Checkbox(
            value=False,
            description=option,
            layout=widgets.Layout(width="auto", max_width="600px"),
            style={"description_width": "initial"},
        )
        for option in quiz.option_map.keys()
    ]

    checkboxes_box = widgets.VBox(checkboxes)
    button = widgets.Button(description="Valider", button_style="success")
    output = widgets.Output()

    def check(b):
        with output:
            output.clear_output()
            selected = {checkbox.description: checkbox.value for checkbox in checkboxes}
            if selected == quiz.option_map:
                print("✅ Correct!")
            else:
                print("❌ Réessaie!")
            c = [selected[k] == quiz.option_map[k] for k in selected.keys()]
            count_true = sum(c)
            score = float(sum(c)) / float(len(c))
            db.insert_score(quiz, score)

    button._click_handlers.callbacks.clear()
    button.on_click(check)

    if quiz.container:
        container = quiz.container()
    else:
        container = None

    if container:
        content = widgets.VBox([checkboxes_box, button, output])
        container.children = [content]
        container.set_title(0, quiz.question)
        display(container)
    else:
        content = widgets.VBox(
            [widgets.HTML(f"<b>{quiz.question}</b>"), checkboxes_box, button, output]
        )
        display(content)


def show(
    quiz: str | int | None = None,
    group: int | None = None,
    container: Callable[[], widgets.Box] | None = None,
):
    """
    Displays quizzes from a JSON file.

    Parameters:
        - quiz [str|int]: URL or filename of the JSON file or the integer identifier of a
          file in a default quiz folder, otherwise a default file is used.
        - group [int]: group of quizzes within the JSON file to display, otherwise all.
        - container: callable that returns an ipwidget container or None.
    """
    try:
        _quiz_url: str

        if not quiz:
            _quiz_url = str(get_project_root() / _marker / "quiz.json")

        elif isinstance(quiz, int):
            _quiz_url = str(get_project_root() / _marker / f"quiz_{quiz}.json")

        else:
            _quiz_url = quiz

        url_parts = urlparse(_quiz_url)

        if url_parts.scheme in ["file", "http", "https"]:
            with urllib.request.urlopen(_quiz_url, timeout=5.0) as url:
                json_obj = json.load(url)

        else:
            with open(_quiz_url, "r") as file_fd:
                json_obj = json.load(file_fd)

        configuration = {
            "container": (
                container or Container(json_obj.get("config", {}).get("container"))
            ),
        }

        context = Context(
            json_obj.get("context", {})
            | {
                "source": _quiz_url,
                "group": group,
            },
        )

        clear_output(wait=True)
        for quiz_json in json_obj.get("quizzes", []):
            quiz_obj = Quiz(quiz_json, context, configuration)
            if quiz_obj.type == QuizType.INVALID:
                continue

            if context.group:
                if context.group not in quiz_obj.groups:
                    continue

            if quiz_obj.type == QuizType.SINGLE_CHOICE:
                create_quiz_pickone(quiz_obj)

            elif quiz_obj.type == QuizType.MULTI_CHOICE:
                create_quiz_select_all_that_apply(quiz_obj)

            else:
                pass

    except OSError as e:
        # print(f"OSError: {e}")
        print("OSError: quiz could not be loaded.")
    except JSONDecodeError as e:
        # print(f"JSONDecodeError: {e}")
        print("JSONError: input is not a invalid JSON.")
    except Exception as e:
        #print(f"Exception: {e}")
        print("Exception: please, ask for help.")
