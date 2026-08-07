import pandas as pd
import os
from typing import Dict
from .config import logger, FILE_PATHS

def check_files_exist(file_paths: Dict[str, str]) -> bool:
    """Verifies that all dataset CSVs exist."""
    all_exist = True
    for name, path in file_paths.items():
        if not os.path.exists(path):
            logger.error(f"Missing file for {name}: {path}")
            all_exist = False
    return all_exist

def extract_data() -> Dict[str, pd.DataFrame]:
    """Reads all dataset CSV files into Pandas DataFrames."""
    logger.info("Extraction Started")
    
    if not check_files_exist(FILE_PATHS):
        logger.warning("Some files are missing. Pipeline will attempt to extract what it can, but downstream tasks might fail if critical files are missing.")
        
    dfs = {}
    for name, path in FILE_PATHS.items():
        logger.info(f"Extracting {name}...")
        try:
            dfs[name] = pd.read_csv(path)
            logger.info(f"Extracted {len(dfs[name])} rows for {name}.")
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
        except pd.errors.EmptyDataError:
            logger.error(f"File is empty: {path}")
        except Exception as e:
            logger.error(f"Error reading {name} at {path}: {str(e)}")
            raise e
            
    logger.info("Extraction Completed Successfully.")
    return dfs
