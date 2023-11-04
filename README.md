# Alfredo
#### Video Demo: <https://youtu.be/HMHKOeKMjMU>
#### Description:

#### Problem
Tracking expenses via Google Sheets provides vast analytical functionalities, but entering data is a lot of manual work (~2-3 hrs per week in my case) and it is not comfortably doable from a mobile phone.

The author's experience with expense-tracking apps has shown they have great UI, but their analytical capabilities are limited. It is a subjective opinion.

---

#### Solution
Alfredo addresses the above-mentioned problem by providing a chatbot interface for entering data to a user-defined Gsheet. Compared to entering data to Gsheets directly, it has the following benefits:

- It can be used via phone which enables adding data on costs via phone as soon as they happen.
- Due to the already mentioned accessibility, no dedicated laptop sessions are required thus the expense tracking can be done in a timelier manner.

---

#### Architecture
Alfredo uses 3 main building blocks:
- [Discord](https://discord.com/) for communicating with users, powered by [discord.py](https://discordpy.readthedocs.io/en/stable/).
    - Chatbot was chosen as a user interface because nowadays people write hundreds messages a day writing a few more is not a big lift for managing one's expenses.
    - Discord was chosen because of there are multiple python libraries for interacting with its API with [discord.py](https://discordpy.readthedocs.io/en/stable/) being an example. On top of that, the project's author uses it for communication with friends.
- [SQLite](https://www.sqlite.org/index.html) database for managing user settings and mapping users to spreadsheets, implemented using [sqlalchemy](https://www.sqlalchemy.org/) ORM.
    - SQLite was chosen because of it is easily configurable and portable.
    - sqlalchemy was chosen because it is the GOTO ORM framework in Python.
- [Google Sheets](https://docs.google.com/spreadsheets) for writing data to user-defined spreadsheets. Relies on [Aiogoogle](https://aiogoogle.readthedocs.io/en/latest/).
    - Google Sheets was chosen because it is the most popular spreadsheet application avaiable at no cost.
    - Aiogoogle was chosed because discord.py is async thus it requires the rest of the code to support it too.

Logic-wise, it can be summarized with the below chart:<br>![Alfredo Bot Logic TLDR](https://github.com/Lifeissimple-zxc/random_stuff/blob/main/Alfredo%20TLDR.png)<br>

Apart from the description above, the bot's code is the best way to understand how it works.


