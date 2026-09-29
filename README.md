
# TicketIQ – AI-Powered Support Ticket Management System

TicketIQ is an AI-powered customer support ticket management system that automates the process of receiving customer emails, creating support tickets, classifying issues, assisting agents with ticket management, and tracking customer-confirmed resolution.

## Problem Statement

Traditional customer support systems often require manual ticket creation, classification, prioritization, and follow-up. This can increase repetitive work and delay response handling.

TicketIQ automates these tasks by converting customer emails into support tickets, applying AI-based classification, and providing an agent dashboard for reviewing and managing tickets.

---

## Key Features

- **Email-to-Ticket Creation**  
  Automatically converts incoming customer emails into support tickets.

- **AI Ticket Classification**  
  Uses a Sentence Transformer model to predict the ticket category and priority.

- **Confidence-Based Review**  
  Low-confidence AI predictions can be reviewed and corrected by the support agent.

- **Agent Ticket Management**  
  Agents can view tickets, review AI predictions, override classifications, manage statuses, and respond to customers.

- **Automatic Acknowledgement**  
  Customers receive an acknowledgement email after their support request is received.

- **Resolution Email**  
  When an agent marks a ticket as resolved, TicketIQ generates and sends a customer-facing resolution email.

- **Customer-Confirmed Closure**  
  Resolved tickets move to "Awaiting Customer" and are closed after the customer confirms that the issue has been resolved.

- **Ticket Reopening**  
  If the customer indicates that the issue is still unresolved, the ticket is reopened for further assistance.

- **Automatic Closure**  
  Tickets that remain in "Awaiting Customer" can be automatically closed after the configured waiting period.

- **Agent Dashboard**  
  Provides an overview of tickets, priorities, categories, and ticket statuses.

---

## System Workflow

```text
Customer Email
      ↓
Gmail Support Inbox
      ↓
Gmail API Synchronization
      ↓
Automatic Ticket Creation
      ↓
AI Classification
      ↓
Category + Priority Prediction
      ↓
Agent Review
      ↓
Issue Resolved by Agent
      ↓
Mark as Resolved
      ↓
AI-Generated Resolution Email
      ↓
Awaiting Customer
      ↓
Customer Replies
      ↓
 ┌───────────────┬────────────────┐
 │ Issue Resolved│ Issue Unresolved│
 ↓               ↓
Closed           Reopened
````

---

## AI Classification

TicketIQ uses a **Sentence Transformer-based text classification approach**.

### Model

```text
Sentence Transformer: all-MiniLM-L6-v2
```

The model converts the ticket subject and message into text embeddings. These embeddings are compared with the trained classification representations to determine the most appropriate ticket category.

### Supported Categories

1. Account, Security & Login
2. App, Website & Feedback
3. Order Modifications & Cancellations
4. Payment & Invoicing
5. Product, Warranty & Tech Specs
6. Returns, Refunds & Exchanges
7. Shipping & Delivery

The system also predicts ticket priority and provides a confidence value for the AI prediction.

### Model Evaluation

The classifier was evaluated on 1,800 samples.

| Metric             | Result |
| ------------------ | -----: |
| Accuracy           | 97.78% |
| Weighted Precision | 97.82% |
| Weighted Recall    | 97.78% |
| Weighted F1 Score  | 97.75% |

These results represent evaluation on the project dataset and should not be interpreted as guaranteed real-world accuracy.

---

## Ticket Lifecycle

```text
New
 ↓
AI Classified
 ↓
Assigned
 ↓
In Progress
 ↓
Resolved
 ↓
Awaiting Customer
 ↓
 ┌───────────────┐
 │               │
Customer confirms    Customer reports issue
 │               │
 ↓               ↓
Closed          Reopened
```

---

## Technology Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* SQLite
* Gmail API
* OpenRouter API

### AI / NLP

* Sentence Transformers
* `all-MiniLM-L6-v2`
* NumPy
* Scikit-learn

### Frontend

* React
* Vite
* Tailwind CSS
* Lucide React

### Development & Tools

* Git
* GitHub
* Swagger / OpenAPI
* VS Code

---

## Project Structure

```text
TicketIQ-v2/
│
├── backend/
│   ├── app/
│   │   ├── ai_drafting.py
│   │   ├── database.py
│   │   ├── gmail_service.py
│   │   ├── gmail_sync.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   ├── ticket_service.py
│   │   └── ticket_workflow.py
│   │
│   ├── data/
│   │   └── ecommerce_support_tickets_dataset.csv
│   │
│   ├── ml/
│   │   ├── artifacts/
│   │   │   └── ticket_classifier.npz
│   │   ├── classifier.py
│   │   └── train_classifier.py
│   │
│   ├── scripts/
│   │   └── reset_development_tickets.py
│   │
│   ├── tests/
│   │   └── test_ticket_workflow.py
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── App.jsx
│       ├── App.css
│       ├── api.js
│       ├── index.css
│       └── main.jsx
│
├── package.json
├── package-lock.json
├── README.md
└── .gitignore
```

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Saanvi666/TicketIQ-v2.git
cd TicketIQ-v2
```

### 2. Backend Setup

Open a terminal and navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file inside the `backend` folder.

Add the required API configuration locally.

**Do not commit `.env` to GitHub.**

### 4. Gmail API Setup

TicketIQ uses the Gmail API for receiving and sending support emails.

The required Gmail OAuth credentials should be configured locally.

The following files must remain private:

```text
backend/credentials.json
backend/token.json
```

These files are excluded through `.gitignore`.

### 5. Run the Backend

From the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend Setup

Open another terminal and navigate to the frontend:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend will then be available through the local Vite development server.

---

## Security

Sensitive credentials are intentionally excluded from the repository.

The `.gitignore` file prevents files such as:

```text
.env
credentials.json
token.json
*.db
.venv/
node_modules/
```

from being committed to GitHub.

API keys and OAuth credentials should always be stored locally and never exposed in the frontend or source control.

---

## Future Scope

Possible future improvements include:

* Individual agent assignment
* PostgreSQL-based production deployment
* Authentication and role-based access control
* Advanced ticket analytics
* Improved multilingual ticket classification
* More detailed customer communication tracking
* Production cloud deployment
* Advanced AI-assisted support workflows

---

## Project Demonstration

A demonstration video showing the complete TicketIQ workflow is included in this repository.

The demonstration covers:

```text
Customer Email
      ↓
Gmail Synchronization
      ↓
Ticket Creation
      ↓
AI Classification
      ↓
Agent Review
      ↓
Mark as Resolved
      ↓
Resolution Email
      ↓
Customer Confirmation
      ↓
Ticket Closed / Reopened
```

---

## Conclusion

TicketIQ provides an integrated workflow for managing customer support requests from initial email reception to final ticket closure.

By combining email integration, AI-based classification, agent review, automated customer communication, and customer-confirmed closure, the system reduces repetitive support tasks while keeping the final decision under human control.

```

