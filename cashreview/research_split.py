"""Research-only grouping checks. Never used as inference features or lookup."""
from collections import defaultdict


def unique_train_contents(manifest):
    buckets=defaultdict(list);groups=defaultdict(set)
    for row in manifest:
        if row.get('error'):raise ValueError('Manifest contains an unresolved technical error')
        buckets[row['sha256']].append(row);groups[row['group']].add(row['split'])
    if any(len(splits)!=1 for splits in groups.values()):raise ValueError('Automatic group crosses splits')
    selected=[]
    for sha,rows in sorted(buckets.items()):
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('Invalid source digest')
        if len({row['split'] for row in rows})!=1:raise ValueError('Identical content crosses splits')
        if len({row['group'] for row in rows})!=1:raise ValueError('Identical content has inconsistent groups')
        if rows[0]['split']!='train':continue
        if len({row['target'] for row in rows})!=1:raise ValueError('TRAIN identical content has conflicting binary supervision')
        if len({row['label_sec'] for row in rows})!=1:raise ValueError('TRAIN identical content has unresolved point supervision')
        if type(rows[0]['target']) is not int or rows[0]['target'] not in [0,1]:raise ValueError('Invalid target')
        representative=dict(rows[0]);representative['manifest_multiplicity']=len(rows);selected.append(representative)
    return selected
