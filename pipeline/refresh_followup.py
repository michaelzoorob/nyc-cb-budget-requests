#!/usr/bin/env python3
"""Apply pipeline/followup_labels.csv to every year's CSV again, without a rebuild.

    refresh_followup.py DATA_DIR

The build adds the follow-up columns from the labels (shared.add_followup). After a relabel
(label_followup/assemble.py --replace), this rewrites only those columns in each year's
"CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv". Rebuild the pages after it.
"""
import glob
import os
import re
import sys

import pandas as pd

from shared import FOLLOWUP_COLS, add_followup

data = sys.argv[1] if len(sys.argv) > 1 else "."
for path in sorted(glob.glob(os.path.join(data, "CB FY20*Requests (all boards, detailed, 2-stage).csv"))):
    fy = re.search(r"FY(\d{4})", path).group(1)
    d = pd.read_csv(path, dtype=str).fillna("")
    new, unlabeled = add_followup(d)
    changed = int((new[FOLLOWUP_COLS] != d[FOLLOWUP_COLS]).any(axis=1).sum())
    new.to_csv(path, index=False)
    print(f"FY{fy}: {changed} of {len(d)} requests changed follow-up; {unlabeled} without a label")
