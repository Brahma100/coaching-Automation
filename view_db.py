import sqlite3
import sys

def view_database(db_path):
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"\n=== Database Analysis: {db_path} ===")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print("No tables found in the database.")
            return
        
        print(f"\nFound {len(tables)} table(s):")
        for table in tables:
            table_name = table[0]
            print(f"\n--- Table: {table_name} ---")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print("Columns:")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, primary_key = col
                pk_indicator = " (PRIMARY KEY)" if primary_key else ""
                null_indicator = " NOT NULL" if not_null else ""
                default_indicator = f" DEFAULT {default_val}" if default_val else ""
                print(f"  - {col_name}: {col_type}{pk_indicator}{null_indicator}{default_indicator}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            print(f"Total rows: {row_count}")
            
            # Show sample data (first 5 rows)
            if row_count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                sample_data = cursor.fetchall()
                
                print("Sample data (first 5 rows):")
                column_names = [desc[1] for desc in columns]
                
                # Print header
                header = " | ".join(column_names)
                print(f"  {header}")
                print(f"  {'-' * len(header)}")
                
                # Print sample rows
                for row in sample_data:
                    row_str = " | ".join([str(val) if val is not None else "NULL" for val in row])
                    print(f"  {row_str}")
            
            print()
        
        conn.close()
        print("\n=== Database analysis complete ===")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    db_file = "coaching.db"
    view_database(db_file)
