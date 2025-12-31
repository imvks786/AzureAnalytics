# Azure Data Factory MySQL Watermark Pipeline
This repository contains an **Azure Data Factory (ADF) pipeline** that loads data into a MySQL database and updates a watermark table to track the last processed timestamp. It handles scenarios where MySQL **primary key conflicts** might occur by using **Post-copy scripts** or Python fallback scripts.

## Table of Contents
- [Overview](#overview)  
- [Architecture](#architecture)  
- [Setup](#setup)  
- [Pipeline Details](#pipeline-details)  
- [Usage](#usage)  
- [Scripts](#scripts)  
- [Notes](#notes)  

## Overview
The project is designed to:
- Load data from a source (e.g., Azure Data Lake, Blob Storage) into MySQL.  
- Maintain a **watermark table** (`watermark`) to track the last processed timestamp per table.  
- Handle **duplicate key issues** in MySQL gracefully using `INSERT ... ON DUPLICATE KEY UPDATE` or Python scripts.  
- Ensure the pipeline is idempotent and safe to run multiple times.
