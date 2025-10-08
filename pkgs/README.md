# Helper Utilities for ENG209

This package provides a set of utilities and modules used in the ENG209 course. These tools include methods such as quiz rendering and visualization aids that help illustrate course concepts — without introducing unnecessary complexity to students.

While some tools (e.g. visualization utilities) go beyond what is directly taught in the course, they are designed to enhance learning without requiring prior knowledge of advanced techniques.

---

## Modules

### Quiz

The `quiz` module enables displaying interactive quizzes in Jupyter notebooks. Students can answer questions directly in the notebook interface. Quizzes are defined using structured JSON documents.

Quizzes are typically displayed in a cell as follows:

```
from eng209 import quiz

quiz.show(quiz='url', group=1, container=quiz.Accordion)
```

All parameters are optional.
If `quiz` is not specified, the default `quiz.json` file in the project folder will be used. If `quiz` is the integer _id_, it will instead load `quiz_{id}.json`.
If `group` is not specified, all quizzes in the file will be shown. Otherwise, only quizzes that belong to the specified group will be included. (A quiz can belong to multiple groups.)
If no container is specified, the system will use the container defined in the JSON file. If none is provided there either, quizzes will default to being stacked vertically.
Currently, only two container types are supported: `quiz.Accordion` and `quiz.Vertical`.

Answering a quiz updates a local database, which can be synched with a remote database to collect the results anonymously and provide comparisons.

#### JSON Structure

Each quiz JSON file consists of two top-level sections:

- **`context`** - global metadata containing useful details about the quizzes
- **`config`** – default configuration options
- **`quizzes`** – the list of quiz entries

The `config` section defines default settings, which can be overridden at the individual quiz level.

---

##### `context.uuid`

- Uniquely identify the source of the quizzes.

##### `context.label`

- A short label for the source of the quizzes.
- Can be used in scoreboards and summary displays.

##### `config.container`

- Sets the default display container for the quizzes.
- Supported values: `"accordion"` or `"none"` (default: `"none"`).
- Can be overridden per quiz.

##### `quizzes[].uuid`

- A **required unique identifier** for the quiz.
- Needed if quiz responses should be collected and shown in a shared scoreboard.

##### `quizzes[].label`

- A short label or title for the quiz.
- Used in scoreboards and summary displays.

##### `quizzes[].question`

- The main question text shown to the student.

##### `quizzes[].options`

- The list of possible answers (or choices) to the question in human readable format.
- Can be either:
  
  - A **list**: Represents a single-answer quiz.
    - The correct answer is defined by the `quizzes[].answer` field.
    - The answer is an integer index (0 = first option, 1 = second, etc.).

  - A **dictionary**: Represents a multiple-choice quiz.
    - Keys are the possible options.
    - Values are booleans: `true` if the option should be selected, `false` otherwise.

##### `quizzes[].groups`

- A list of **group IDs** (integers) that determine which quizzes are grouped together in the same display container.
- Useful for:
  - Rendering multiple quizzes in a single notebook cell.
  - Triggering group-based actions (e.g. submitting answers for the whole group).

##### `quizzes[].container`

- Overrides the `config.container`
---