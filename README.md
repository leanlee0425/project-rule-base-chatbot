# README – OUM Final Year Project - E-Commerce System Application (Rule-Based Chatbot) - LEE YEN YEN (BIT May 2025 Semester) 

This project is aim to develop a **rule-based chatbot** for e-commerce platform to enhance customer interaction and provide timely support. There are 3 types of chatbot which suit for different use case and needed of advance technical skills, such as rule-based chatbot, machine learning chatbot, hybrid chatbot and virtual assistance chatbot. I am choosing rule-based chatbot for this project due to its simplicity, ease of implementation, and repetitive queries commonly found in e-commerce customer service.

---

## System Implementation and Testing

This section describes the overall system implementation, installation guide, testing process, and main function codes for the chatbot project.

### System Overview

The system includes two main parts:

1. **docs (frontend)** – A simple e-commerce interface with pages such as Home, Shop, Contact, Cart, and Checkout, along with the stylist CSS folder and JS folder.
2. **backend (Chatbot API)** – A FastAPI service that handles user messages, matches keywords or regex patterns, and provides automated responses.

The chatbot connects the user’s input to the SQLite knowledge base to retrieve the correct responses based on predefined rules.

---

## System Guide / Manual

* Users can access the chatbot through the e-commerce website’s chat icon.
* Type a question or message such as “Where is my order?” or “How to refund?”.
* The chatbot will match the message with the keyword or regex in the database and reply automatically.
* If no match is found, a fallback menu will appear.

Admin can update the chatbot database through SQLite to add, modify, or delete FAQ rules and responses.

---

## Installation Manual

### Prerequisites

* Python 3.10+
* Git
* IDE (Strongly recommended Visual Studio Code)
* SQLite

### Steps

**1. Clone Repository:**

Have 2 ways to clone repository:

**a) Using commands**
   ```bash
   git clone <your-repo-url>
   cd <repo>
   ```
**b) Navigate to Github Page > Code > Download ZIP**

**2. Set Up Backend:**

   ```bash
   cd backend
   python -m venv .venv
   . .venv/Scripts/activate   # Windows
   pip install -r requirements.txt
   ```

   Navigate to **app.py**, add the following two lines for live in your local
   ```bash
    allow_origins=[
        "https://leanlee0425.github.io",
        "http://127.0.0.1:5500"
        ,"http://localhost:5500"
        ,"http://127.0.0.1:8080" << This
        ,"http://localhost:8080" << This
    ],
   ```

**3. Run the Server:**

From the VS, create "New Terminal" > navigate to backend folder
   ```bash
   uvicorn app:app --reload --port 8000
   ```
You can test it to navigate to your local "http://127.0.0.1:8000/", if the webpage shows as {"status":"OK"} means your chatbot is ready. You can navigate to your 1st Terminal to setup the frontend.

**4. Set Up Frontend:**

   * Run local preview:

     ```bash
     cd docs
     python -m http.server 8080
     ```
   * Visit: `http://127.0.0.1:8080`
Boom! You will see the website interface with the chatbot widget.

**5. Deployment (Optional):**

   * Deploy backend to Render (https://render.com/), you would need to sign up an account.
   * Need to connect with your Github Repo, remember to make your repo as Public.
   * Deploy frontend to GitHub Pages (set the source folder to `/frontend`).

---

## Main Function Codes

### 1. app.py

Creates and runs the FastAPI app, registers routers, and enables CORS.

### 2. FYP_chatbot_LEE_YEN_YEN.py

Contain the main chatbot logic, which are:
* SQL to retrieve data
* Handles keyword and regex rule matching to identify the best response
* Fallback mechanism

### 3. chatbot_db.db

Initializes and connects to the SQLite database for storing FAQs and orders.

### 4. chat.js

Sends and receives messages from the FastAPI backend and renders chat messages on the frontend.

### 5. config.js

Chatbot router.

---

**End of README**
