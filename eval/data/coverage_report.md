# Coverage Report (frozen full set)

- Total queries: 100  (tiers: {'simple': 40, 'cross_modal': 30, 'multi_hop': 30})
- Probes: {'no_tool': 5, 'unavailable_modality': 5}
- Queries per patient: {'P0001': 9, 'P0002': 11, 'P0003': 10, 'P0004': 10, 'P0005': 10, 'P0006': 10, 'P0007': 10, 'P0008': 10, 'P0009': 10, 'P0010': 10}
- Gold-agent (required) modality coverage: {'ecg': 37, 'lab_results': 30, 'medication': 17, 'chest_xray': 12, 'clinical_notes': 30, 'echo': 45, 'heart_sounds': 24}

- KB sets: 40  (clean 10, seeded 30)
- Seeded subtlety distribution: {'blatant': 9, 'moderate': 13, 'subtle': 8}
- Seeded conflict-pair distribution: 9 distinct pairs
    - ['chest_xray', 'clinical_notes']: 2
    - ['chest_xray', 'echo']: 2
    - ['clinical_notes', 'ecg']: 1
    - ['clinical_notes', 'echo']: 3
    - ['clinical_notes', 'lab_results']: 7
    - ['ecg', 'echo']: 7
    - ['ecg', 'heart_sounds']: 2
    - ['ecg', 'lab_results']: 2
    - ['echo', 'heart_sounds']: 4
