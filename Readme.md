# TrackKit - From Clicks to Clarity


## Overview
This project demonstrates an end-to-end data engineering and analytics solution built using Azure Data Factory (ADF), Azure Databricks, Parquet storage, and a custom web analytics dashboard. The solution covers:
- Incremental data ingestion using ADF
- Data transformation and optimization using Databricks
- Parquet-based storage design
- API-driven processing using IP datasets
- Web analytics UI for real-time and historical insights


## High-Level Architecture
- Source SQL Database
- Azure Data Factory Pipeline
- Azure Data Lake Storage (ADLS)
- Azure Databricks (Transformation Layer)
- Downstream APIs & Analytics Dashboard

# Azure Data Factory Pipeline
## Pipeline Flow
1. Lookup – Last Processed Date: Fetches the watermark / last processed timestamp for incremental load.
2. Copy Data – Raw to ADLS: Copies incremental SQL data into ADLS (raw zone).
3. Databricks Notebook Activity: Reads raw SQL data
4. Performs transformations: Converts data into optimized Parquet format
5. Parquet Output Split:
- TechStack Parquet: Structured tech stack analytics data
- IP List Parquet: Cleaned list of IP addresses used by downstream APIs
6. Execute Pipeline – IP Processing, Triggers a child pipeline to process IP-based API calls using the IP Parquet dataset.
7. Copy Data – TechStack to DB, Loads curated Parquet data into the analytics database.
8. Update Watermark (Web Activity): Updates the last processed timestamp.
9. Send Notification (Web Activity): Sends completion email notification.


## Databricks Transformation Logic
In Azure Databricks, SQL data is transformed and written into two Parquet datasets:
1. TechStack Parquet:
- Normalized and analytics-ready
- Used for reporting, dashboards, and rule analysis
- Optimized for read performance
2. IP Address Parquet
- Contains unique and cleaned IP addresses
- Used by ADF ForEach + Web/API activities
- Enables scalable API invocation without re-querying SQL
## Benefits of Parquet:
- Columnar storage
- Compression
- Faster analytics queries
- Lower storage cost

## API Processing (ADF ForEach)
- ADF Lookup reads IP list from Parquet
- ForEach activity iterates over IPs
- Web/API activity fetches enrichment data per IP
- Results are stored back into the analytics system

# Analytics Dashboard Features
Property & Data Stream Management (Frontend – Google Analytics Style). This project follows a Google Analytics–like property model on the frontend.

**1. Create a Property:** 
A Property represents a logical container for measurement data.
- Each property holds analytics data for one or more websites
- A unique Site ID is generated per property
- All events, page views, and rules are linked to this property

**2. Set Up Data Stream:** A Web Data Stream is configured for each website under a property to start collecting events.

**Web Stream Configuration:**
- Website URL: https://john.in
- Stream Name: Main Website

**Default Measurements Enabled:**
- Page Views
- Scroll Tracking
- Outbound Clicks
- First Visit
- Form Submissions

These events are captured automatically without additional configuration.

**3. Installation Instructions:** To start tracking, install the analytics script on your website.

**Manual Installation**
- Copy and paste the following tag immediately after the <head> element on every page of your website.
- Do not add more than one tag per page.
- data-site-id uniquely identifies your property
- Script automatically initializes tracking
- Events are sent securely to the analytics backend

## Real-Time Overview
* Active users (5 min / 30 min)
* Page views
* Bounce rate
* Session duration

## Referrer Analysis
* Direct
* Google / Bing
* External URLs

## Tech Details
* Browser distribution
* Operating system breakdown
* Device category (Desktop / Mobile)
* Screen resolution analytics

## Rule Management
* Create custom tracking rules
* CSS selector-based event tracking
* Enable/disable rules dynamically

## Rule Analysis
* Click counts per rule
* Last click timestam
* Selector-level insights

## Tech Stack
* Azure Data Factory
* Azure Databricks
* Azure Data Lake Storage (ADLS)
* SQL Database
* REST APIs
* Custom Analytics Web Dashboard

# Use Cases
* Website analytics tracking
* User behavior analysis
* IP-based enrichment
* Rule-based event tracking
* Scalable data engineering pipelines

# Author
Vivek Singh
