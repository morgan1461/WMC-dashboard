# WMC Dashboard

## Overview
This project provides dashboard data for The Ohio State University Medical Center Shuttle. This code is adapted from legacy R code used in The Ohio State University Department of Transportation and Traffic Management.

## Key Components

---

### File Structure
```
.
├── stops
│   ├── pattern_stops.csv
│   └── stop_inventory.csv
├── busstate_cleaned
│   └── 
├── dashboard_data
│   ├── 2025
│   ├── 2026
│   └── Med Ctr Expr Dashboard - Template
├── modules
│   ├── busstate_processing.py
│   ├── headway.py
│   ├── capacity.py
│   ├── travel_time.py
│   ├── combine_uh_doan_stops.py
│   └── med_center_dashboard_metrics.py
├── busstate_processing_pipeline.ipynb
├── med_center_dashboard_metrics.ipynb
├── .gitignore
└── README.md
```


---

### BusState File Processing

The `busstate_processing_pipeline.ipynb` and `busstate_processing.py` modules function as **standalone busstate file processors**. They are designed to:
- Process and clean busstate data independently
- Be easily adapted and repurposed for future use cases

This modular architecture should allow these processors to be utilized in other future projects or workflows.

---

### Med Center Express Shuttle Metrics Calculations

`med_center_dashboard_metrics.ipynb` contains the modules from `headway.py`, `capacity.py`, `travel_time.py`, `combine_uh_doan_stops.py`, and `med_center_dashboard_metrics.py`. These functions are modular and should be able to be edited relatively independently as necessary. 
Descriptions of the modules:
- `headway.py`: Builds headway summary table for final report
- `capacity.py`: Builds capacity summary table for final report
- `travel_time.py`: Build travel time summary table for final report
- `combine_uh_doan_stops.py`: Helper function to combine the University Hospital and Doan Hall stops for downstream calculations
-  `med_center_dashboard_metrics.py`: Controller module to run process in proper order

---

### Author
Clayton Morgan (Morgan.1461) Reporting and Analytics Analyst at The Ohio State University Department of Transportation and Traffic Management