from src.seed_data import questions_par_section


def test_seed_data_converted_structure_is_dict_with_int_keys_and_lower_values():
    first_section = next(iter(questions_par_section))
    section_map = questions_par_section[first_section]

    assert isinstance(section_map, dict)
    assert all(isinstance(k, int) for k in section_map.keys())
    assert all(isinstance(v, str) and v == v.lower() for v in section_map.values())
