# Alfredo
#### Video Demo:  <URL HERE>
#### Description:

#### Problem

Tracking expenses via Google Sheet provides great analytical capabilities, but entering data means a lot of manual work (~2-3 hrs per week) which is not doable from a mobile phone.

The author's experience with expense tracking apps has shown they have great UI, but their analytical capabilities are limited. It is a subjective opinion.

---

#### Solution
Alfredo addresses the above-mentioned problem by providing a chatbot interface for entering data to a user-defined Gsheet. Compared to entering data to Gsheets directly, it has the following benefits:

- It can be used via phone which enables adding data on costs via phone as soon as they happen.
- Due to the already mentioned accessibility, no dedicated laptop sessions are required thus the expense tracking can be done in a timelier manner.

---
#### Architecture
Alfredo uses 3 main building blocks:
- Discord for communicating with users, powered by [discord.py](https://discordpy.readthedocs.io/en/stable/).
- [SQLite](https://www.sqlite.org/index.html) database for managing user settings and mapping users to spreadsheets, implemented using [sqlalchemy](https://www.sqlalchemy.org/) ORM.
- [Google Sheets](https://docs.google.com/spreadsheets) for writing data to user-defined spreadsheets. Relies on [Aiogoogle](https://aiogoogle.readthedocs.io/en/latest/).

Logic-wise, it can be summarized with the below chart:<br>![Alfredo Bot Logic TLDR](https://github.com/Lifeissimple-zxc/random_stuff/blob/main/Alfredo%20TLDR.png)<br>

Apart from the description above, the bot's code is the best way to understand how it works, no point if further writing here.



