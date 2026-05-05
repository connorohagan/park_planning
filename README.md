# Park Placement Tool

## How to run

### 1. pip install -r requirements.txt

### 2. Data Paths

Ensure data is downloaded.

In config.py check file paths for:

LSOA_GPKG_PATH
POP_XLSX_PATH
WALES_RIVERS_SEA_GPKG
WALES_SURFACEWATER_GPKG

Choose study area, example:
place = "Cardiff, Wales, UK"

Choose walk cutoff distance:
WALK_CUTOFF_M

Choose which presets to run by editing:
SCORING_PRESETS


### 3. Output folders

Before running the tool, make sure to have output folders:

outputs/selected_sites  
outputs/all_candidate_scores
outputs/run_summaries

### 4. Run the tool

python -m park_planning.main

You will be asked what stopping criteria to use, select this in the command line.

### 5. Output

View numerical output in the outputs folder
View interactive map from: output_index.html