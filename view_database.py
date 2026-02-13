#!/usr/bin/env python3
"""
SQLite Database Viewer Script
A Python script to explore and view data in SQLite databases
"""

import sqlite3
import sys
import os
from pathlib import Path

def connect_to_database(db_path):
    """Connect to SQLite database"""
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def list_tables(conn):
    """List all tables in the database"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        return [table[0] for table in tables]
    except sqlite3.Error as e:
        print(f"Error listing tables: {e}")
        return []

def get_table_schema(conn, table_name):
    """Get schema information for a table"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return columns
    except sqlite3.Error as e:
        print(f"Error getting table schema: {e}")
        return []

def get_table_count(conn, table_name):
    """Get row count for a table"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        return count
    except sqlite3.Error as e:
        print(f"Error getting table count: {e}")
        return 0

def preview_table_data(conn, table_name, limit=5):
    """Preview first few rows of a table"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Error previewing table data: {e}")
        return []

def export_table_to_csv(conn, table_name, output_file=None):
    """Export table data to CSV file"""
    import csv
    
    if output_file is None:
        output_file = f"{table_name}_export.csv"
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            
            # Write headers
            column_names = [description[0] for description in cursor.description]
            csv_writer.writerow(column_names)
            
            # Write data
            csv_writer.writerows(cursor.fetchall())
        
        print(f"Table '{table_name}' exported to '{output_file}'")
        return True
    except Exception as e:
        print(f"Error exporting table: {e}")
        return False

def interactive_database_explorer(db_path):
    """Interactive database exploration"""
    conn = connect_to_database(db_path)
    if not conn:
        return
    
    print(f"\n=== SQLite Database Explorer ===")
    print(f"Database: {db_path}")
    print(f"File size: {os.path.getsize(db_path) / (1024*1024):.2f} MB")
    
    # List tables
    tables = list_tables(conn)
    if not tables:
        print("No tables found in database.")
        conn.close()
        return
    
    print(f"\nFound {len(tables)} table(s):")
    for i, table in enumerate(tables, 1):
        count = get_table_count(conn, table)
        print(f"  {i}. {table} ({count:,} rows)")
    
    while True:
        print("\n=== Options ===")
        print("1. View table schema")
        print("2. Preview table data")
        print("3. Export table to CSV")
        print("4. Run custom SQL query")
        print("5. Show database info")
        print("0. Exit")
        
        choice = input("\nSelect option (0-5): ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            table_name = select_table(tables)
            if table_name:
                show_table_schema(conn, table_name)
        elif choice == '2':
            table_name = select_table(tables)
            if table_name:
                show_table_preview(conn, table_name)
        elif choice == '3':
            table_name = select_table(tables)
            if table_name:
                export_table_to_csv(conn, table_name)
        elif choice == '4':
            run_custom_query(conn)
        elif choice == '5':
            show_database_info(conn, db_path)
        else:
            print("Invalid option. Please try again.")
    
    conn.close()
    print("Database connection closed.")

def select_table(tables):
    """Helper function to select a table"""
    print("\nAvailable tables:")
    for i, table in enumerate(tables, 1):
        print(f"  {i}. {table}")
    
    try:
        choice = int(input("Select table number: ").strip())
        if 1 <= choice <= len(tables):
            return tables[choice - 1]
        else:
            print("Invalid table number.")
            return None
    except ValueError:
        print("Please enter a valid number.")
        return None

def show_table_schema(conn, table_name):
    """Display table schema"""
    schema = get_table_schema(conn, table_name)
    print(f"\n=== Schema for table '{table_name}' ===")
    print(f"{'Column':<20} {'Type':<15} {'NotNull':<8} {'Default':<15} {'PK':<3}")
    print("-" * 65)
    
    for column in schema:
        cid, name, col_type, not_null, default_val, pk = column
        not_null_str = "YES" if not_null else "NO"
        default_str = str(default_val) if default_val is not None else ""
        pk_str = "YES" if pk else "NO"
        print(f"{name:<20} {col_type:<15} {not_null_str:<8} {default_str:<15} {pk_str:<3}")

def show_table_preview(conn, table_name):
    """Display table data preview"""
    rows = preview_table_data(conn, table_name)
    schema = get_table_schema(conn, table_name)
    
    print(f"\n=== Preview of table '{table_name}' (first 5 rows) ===")
    
    if not rows:
        print("No data found in table.")
        return
    
    # Print column headers
    headers = [col[1] for col in schema]
    print(" | ".join(f"{header:<15}" for header in headers))
    print("-" * (len(headers) * 17))
    
    # Print data rows
    for row in rows:
        print(" | ".join(f"{str(val):<15}" for val in row))

def run_custom_query(conn):
    """Run a custom SQL query"""
    print("\n=== Custom SQL Query ===")
    print("Enter your SQL query (or 'back' to return):")
    query = input("> ").strip()
    
    if query.lower() == 'back':
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        
        if query.upper().startswith('SELECT'):
            results = cursor.fetchall()
            if results:
                # Print column headers if available
                if cursor.description:
                    headers = [desc[0] for desc in cursor.description]
                    print(" | ".join(f"{header:<15}" for header in headers))
                    print("-" * (len(headers) * 17))
                
                # Print results
                for row in results:
                    print(" | ".join(f"{str(val):<15}" for val in row))
                print(f"\n{len(results)} row(s) returned.")
            else:
                print("No results returned.")
        else:
            conn.commit()
            print(f"Query executed successfully. {cursor.rowcount} row(s) affected.")
    
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")

def show_database_info(conn, db_path):
    """Show database information"""
    print(f"\n=== Database Information ===")
    print(f"File: {db_path}")
    print(f"Size: {os.path.getsize(db_path) / (1024*1024):.2f} MB")
    
    # Get SQLite version
    cursor = conn.cursor()
    cursor.execute("SELECT sqlite_version()")
    version = cursor.fetchone()[0]
    print(f"SQLite Version: {version}")
    
    # Get table count and total rows
    tables = list_tables(conn)
    total_rows = 0
    print(f"\nTables: {len(tables)}")
    
    for table in tables:
        count = get_table_count(conn, table)
        total_rows += count
        print(f"  - {table}: {count:,} rows")
    
    print(f"Total rows across all tables: {total_rows:,}")

def main():
    """Main function"""
    # Check if database file exists
    db_file = "coaching.db"
    
    if not os.path.exists(db_file):
        print(f"Database file '{db_file}' not found in current directory.")
        print("Please make sure the database file exists and try again.")
        return
    
    print("SQLite Database Viewer")
    print("=====================")
    
    # Start interactive exploration
    interactive_database_explorer(db_file)

if __name__ == "__main__":
    main()