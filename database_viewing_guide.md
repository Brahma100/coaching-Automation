# Database Viewing Solutions for SQLite Database

## Database Information
- **File:** coaching.db
- **Type:** SQLite Database
- **Size:** 9.7 MB
- **Location:** Root directory of workspace

## Recommended Database Viewing Tools

### 1. GUI Applications (Recommended for Beginners)

#### A. DB Browser for SQLite (Free & Popular)
- **Download:** https://sqlitebrowser.org/
- **Features:** 
  - User-friendly interface
  - Browse tables and data
  - Execute SQL queries
  - Import/Export data
  - Visual schema designer
- **Installation:** Download installer for Windows and run
- **Usage:** Open DB Browser → File → Open Database → Select coaching.db

#### B. DBeaver (Universal Database Tool)
- **Download:** https://dbeaver.io/download/
- **Features:**
  - Supports multiple database types
  - Advanced SQL editor
  - Data visualization
  - ER diagrams
  - Export to various formats
- **Installation:** Download Community Edition for Windows
- **Usage:** New Connection → SQLite → Browse to coaching.db

#### C. SQLiteStudio (Lightweight)
- **Download:** https://sqlitestudio.pl/
- **Features:**
  - Portable (no installation required)
  - Multiple database support
  - SQL syntax highlighting
  - Data export/import
- **Usage:** Download portable version → Run → Database → Add database → coaching.db

### 2. Command Line Tools

#### A. SQLite3 Command Line
- **Installation:** Download from https://sqlite.org/download.html
- **Windows:** Download sqlite-tools-win32-x86-*.zip
- **Usage:**
  ```bash
  # Navigate to database directory
  cd path/to/database
  
  # Open database
  sqlite3 coaching.db
  
  # List all tables
  .tables
  
  # Show table schema
  .schema table_name
  
  # Query data
  SELECT * FROM table_name LIMIT 10;
  
  # Exit
  .quit
  ```

### 3. VS Code Extensions

#### A. SQLite Viewer
- **Extension ID:** qwtel.sqlite-viewer
- **Installation:** VS Code → Extensions → Search "SQLite Viewer" → Install
- **Usage:** Right-click on coaching.db → "Open with SQLite Viewer"

#### B. SQLite Explorer
- **Extension ID:** alexcvzz.vscode-sqlite
- **Installation:** VS Code → Extensions → Search "SQLite Explorer" → Install
- **Usage:** Explorer panel → SQLite Explorer → Add Database → Select coaching.db

#### C. Database Client JDBC
- **Extension ID:** cweijan.vscode-database-client2
- **Features:** Universal database client for VS Code
- **Usage:** Command Palette → "Database: Add Connection" → SQLite → Select file

### 4. Web-Based Tools

#### A. phpLiteAdmin (If you have a web server)
- **Download:** https://www.phpliteadmin.org/
- **Requirements:** PHP web server
- **Usage:** Upload phpLiteAdmin.php to web directory, access via browser

### 5. Python Scripts (For Developers)

#### A. Using Python sqlite3 module
```python
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('coaching.db')

# List all tables
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [table[0] for table in tables])

# Read data into pandas DataFrame
df = pd.read_sql_query("SELECT * FROM table_name LIMIT 10", conn)
print(df)

# Close connection
conn.close()
```

## Installation Priority (Recommended Order)

### For Non-Technical Users:
1. **DB Browser for SQLite** - Easiest to use
2. **VS Code SQLite Viewer Extension** - If using VS Code

### For Developers:
1. **DBeaver** - Most powerful features
2. **SQLite3 Command Line** - For scripting
3. **VS Code Database Client** - Integrated development

### For Quick Viewing:
1. **VS Code SQLite Viewer Extension** - Instant viewing
2. **SQLiteStudio Portable** - No installation required

## Quick Start Commands

### Windows PowerShell (After installing SQLite3)
```powershell
# Download SQLite3 tools
Invoke-WebRequest -Uri "https://sqlite.org/2024/sqlite-tools-win32-x86-3460000.zip" -OutFile "sqlite-tools.zip"
Expand-Archive -Path "sqlite-tools.zip" -DestinationPath "sqlite-tools"

# Add to PATH or use full path
.\sqlite-tools\sqlite3.exe coaching.db ".tables"
```

### Using Python (if available)
```python
import sqlite3

# Quick database exploration
conn = sqlite3.connect('coaching.db')
cursor = conn.cursor()

# Get table list
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())

# Get table info
cursor.execute("PRAGMA table_info(your_table_name)")
print("Columns:", cursor.fetchall())

conn.close()
```

## Troubleshooting

### Common Issues:
1. **File not found:** Ensure you're in the correct directory
2. **Permission denied:** Check file permissions
3. **Corrupted database:** Try `.recover` command in sqlite3
4. **Large file:** Use LIMIT in queries to avoid memory issues

### Performance Tips:
- Use LIMIT for large tables
- Index frequently queried columns
- Use EXPLAIN QUERY PLAN for optimization

## Data Export Options

### From DB Browser:
- File → Export → Table(s) as CSV
- File → Export → Database to SQL file

### From Command Line:
```bash
# Export to CSV
sqlite3 coaching.db
.headers on
.mode csv
.output data.csv
SELECT * FROM table_name;
.quit
```

### From Python:
```python
import pandas as pd
import sqlite3

conn = sqlite3.connect('coaching.db')
df = pd.read_sql_query("SELECT * FROM table_name", conn)
df.to_csv('exported_data.csv', index=False)
conn.close()
```

This guide provides multiple options to view and interact with your SQLite database, from simple GUI tools to advanced command-line operations.