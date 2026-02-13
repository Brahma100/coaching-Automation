# Database Analysis Report: coaching.db

## Overview
**Database File:** `coaching.db`  
**Database Type:** SQLite  
**Total Tables:** 38  
**Analysis Date:** 2026-02-11  
**Database Version:** 20260211_0018 (from alembic_version)

## Database Purpose
This is a comprehensive coaching/education management system database that tracks:
- Student enrollment and attendance
- Class scheduling and session management
- Fee collection and payment tracking
- Teacher workflow and action items
- Communication logs and notifications
- Risk assessment and student analytics

## Table Structure Overview

### 1. Core Entity Tables

#### Students & Parents
- **students** (36 records): Student profiles with contact preferences
- **parents** (36 records): Guardian information with phone and telegram details
- **parent_student_map** (36 records): Relationships between parents and students

#### Academic Structure
- **batches** (3 records): Class groups (Physics_9, Chemistry_10, Maths_12)
- **rooms** (3 records): Physical/virtual classroom spaces
- **batch_schedules** (9 records): Weekly class timing schedules
- **class_sessions** (58 records): Individual class instances with topics and status

#### Administrative
- **auth_users** (1 record): System authentication for teachers/staff
- **allowed_users** (1 record): Authorized system users
- **staff_users** (0 records): Staff management (empty)

### 2. Operational Data Tables

#### Attendance & Performance
- **attendance_records** (660 records): Daily attendance tracking
- **student_dashboard_snapshot** (36 records): Student performance summaries
- **student_risk_profiles** (0 records): Risk assessment data (empty)
- **student_risk_events** (0 records): Risk level change history (empty)

#### Financial Management
- **fee_records** (72 records): Payment tracking and UPI links
- **offers** (0 records): Discount and promotion management (empty)
- **offer_redemptions** (0 records): Applied discounts (empty)
- **referral_codes** (0 records): Student referral system (empty)

#### Academic Content
- **homework** (0 records): Assignment management (empty)
- **homework_submissions** (0 records): Student submissions (empty)
- **programs** (0 records): Course programs (empty)
- **boards** (0 records): Educational boards (empty)
- **class_levels** (0 records): Grade levels (empty)
- **subjects** (0 records): Subject catalog (empty)

### 3. Workflow & Communication Tables

#### Task Management
- **pending_actions** (509 records): Teacher follow-up tasks and reviews
- **action_tokens** (18,258 records): Secure tokens for session summaries
- **rule_configs** (0 records): Automation rule settings (empty)

#### Communication System
- **communication_logs** (56 records): Telegram/SMS message history
- **teacher_today_snapshot** (1 record): Daily teacher dashboard data
- **admin_ops_snapshot** (1 record): System health and alerts

#### System Management
- **backup_logs** (0 records): Database backup history (empty)
- **calendar_overrides** (0 records): Schedule modifications (empty)

## Key Data Insights

### Active Operations
1. **High Activity System**: 509 pending actions indicating active workflow management
2. **Extensive Communication**: 18K+ action tokens and 56 communication logs
3. **Regular Classes**: 58 completed sessions across 3 batches
4. **Student Engagement**: 660 attendance records showing consistent tracking

### System Health
- **Overdue Actions**: 209 overdue actions across teachers (from admin snapshot)
- **Automation Issues**: Some notification failures in post-class summaries
- **Student Risk**: 13 low-attendance students identified

### Financial Status
- **Fee Collection**: Active tracking with UPI payment links
- **Outstanding Dues**: Multiple students with pending payments
- **Batch Distribution**: 
  - Physics_9: 30 max students
  - Chemistry_10: 28 max students  
  - Maths_12: 24 max students (online)

## Sample Data Examples

### Student Information
```
ID: 1, Name: Riya Sinha, Phone: 9100000101, Batch: Physics_9
ID: 2, Name: Kavya Bedi, Phone: 9100000102, Batch: Chemistry_10
ID: 3, Name: Tara Saxena, Phone: 9100000103, Batch: Maths_12
```

### Recent Sessions
```
Session 1: Motion in a Straight Line (Physics_9) - Completed
Session 2: Light Reflection (Physics_9) - Completed  
Session 3: Sound Waves (Physics_9) - Completed
```

### Pending Actions (Sample)
```
- Review session summary for Session 1 (Overdue: 728 hours)
- Follow up absentee: Aditya Mehta (Overdue: 706 hours)
- Follow up absentee: Aadhya Menon (Overdue: 706 hours)
```

## Database Schema Highlights

### Well-Designed Features
1. **Comprehensive Tracking**: Attendance, fees, communication, and workflow
2. **Flexible Scheduling**: Support for both online and offline classes
3. **Risk Management**: Student risk profiling and event tracking
4. **Automation Ready**: Token-based secure links and rule configurations
5. **Multi-Channel Communication**: SMS, Telegram, and in-app notifications

### Areas for Optimization
1. **Unused Tables**: Several empty tables (homework, programs, subjects)
2. **Action Backlog**: High number of overdue pending actions
3. **Risk Profiles**: Risk assessment system not yet populated
4. **Referral System**: Referral and offer systems not implemented

## Recommendations

1. **Immediate Action**: Address the 209 overdue actions to improve workflow efficiency
2. **System Cleanup**: Review and potentially remove unused table structures
3. **Risk Implementation**: Activate student risk profiling for better intervention
4. **Automation Enhancement**: Fix notification failures in post-class summaries
5. **Data Archival**: Consider archiving old action tokens and communication logs

## Technical Notes

- **Database Migration**: Uses Alembic for version control (current: 20260211_0018)
- **Security**: Token-based authentication with secure session links
- **Performance**: Large action_tokens table (18K+ records) may need indexing
- **Backup Strategy**: Backup logging system in place but currently empty

This database represents a mature, feature-rich coaching management system with active usage patterns and comprehensive data tracking capabilities.