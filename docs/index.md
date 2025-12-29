# Welcome to Omniproctor

!!! info "Project Status"
    This project is currently a **Work In Progress (WIP)**. Features and documentation are actively being developed and improved.

## Overview

Welcome to **Omniproctor** - a comprehensive online assessment and proctoring platform designed to conduct secure, monitored examinations in a controlled digital environment.

## What is Omniproctor?

Omniproctor is a full-stack proctoring solution that combines a **secure browser application** with a **web-based dashboard** to provide end-to-end management of online assessments. 

### Key Features

- **Secure Browser**: Custom PyQt6-based browser with built-in proctoring controls
- **Network Isolation**: Automated firewall configuration to restrict network access during exams
- **Kiosk Mode**: Prevents users from switching to other applications
- **Dashboard Management**: Web-based interface for creating and managing tests
- **User Management**: Role-based access control for administrators and test-takers
- **Real-time Monitoring**: Track active tests and user activities

## System Components

### 1. Browser Application
A standalone desktop application built with PyQt6 that provides:
- Secure web browsing with restricted access
- Kiosk mode to prevent task switching

### 2. Dashboard (Web Application)
A full-stack web application consisting of:
- **Backend**: Node.js/Express REST API with Prisma ORM
- **Frontend**: React-based built with Vite and TailwindCSS
- **Database**: PostgreSQL for storing users, tests, and activity logs

## Getting Started

### Prerequisites

- **For Browser Application**:
    - Windows OS
    - Python 3.8 or higher
    - Administrator privileges (for firewall control)
    - **SimpleWall must be installed before setting up the browser** (for network restrictions)
    (This will be removed in future update and the browser will not depend on any external firewall)

!!! warning "SimpleWall Required (Temporary Workaround)"
    The browser application currently requires [SimpleWall](https://www.simplewall.org/) to be installed and configured on your system.

    **Why?** Due to time constraints and the complexity of implementing custom Windows Filtering Platform (WFP) drivers, we are using SimpleWall as a temporary solution for network isolation. This external dependency will be removed and replaced with native firewall rules in future updates.

- **For Dashboard**:
    - Node.js 16 or higher
    - PostgreSQL database
    - npm or yarn package manager

### Quick Start

#### 1. Setting Up the Dashboard

**Backend Setup:**

```bash
cd Dashboard/Backend
npm install
npx prisma migrate deploy
node src/index.js
```

**Frontend Setup:**

```bash
cd Dashboard/Frontend
npm install
npm run dev
```

#### 2. Running the Browser Application


```bash
cd Browser
pip install -r requirements.txt
python main.py
```

#### 3. Initial Login

1. Access the dashboard at `http://localhost:5173` (or configured port)
2. Login with your credentials
3. Create or join a test
4. Launch the secure browser for taking assessments

## Project Structure

```
Omniproctor/
├── Browser/                 # Secure browser application
│   ├── main.py             # Main launcher with authentication
│   ├── browser/            # Core browser implementation
│   │   ├── main.py         # Browser engine with security features
│   │   ├── keyblocks.py    # Keyboard/hotkey blocking
│   │   └── network/        # Network control modules
│   └── pyproject.toml      # Python dependencies
│
├── Dashboard/
│   ├── Backend/            # REST API server
│   │   ├── src/
│   │   │   ├── controllers/  # Request handlers
│   │   │   ├── routes/       # API endpoints
│   │   │   ├── middlewares/  # Auth & validation
│   │   │   └── config/       # Database config
│   │   └── prisma/           # Database schema & migrations
│   │
│   └── Frontend/           # React web application
│       └── src/
│           ├── pages/        # Dashboard, Login, Tests
│           ├── components/   # Reusable UI components
│           └── context/      # Auth state management
│
└── docs/                   # Documentation (MkDocs)
```

## Rules and Guidelines

!!! warning "Important Rules"
    - The browser must be launched with administrator privileges for full security features
    - Ensure stable internet connection before starting a test
    - Report any technical issues immediately to administrators

## Support

For technical support or bug reports, please contact the development team or create an issue in the project repository.
