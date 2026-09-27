"""Exact authored membership for an isolated foundation review."""

def foundation_review_members(pieces, role_prefix=None, component_group=None):
    if bool(role_prefix) == bool(component_group):
        raise ValueError('Choose exactly one foundation review scope.')
    if role_prefix:
        return {p['name'] for p in pieces if p['role'].startswith(role_prefix)}
    if component_group == 'petticoats':
        return {p['name'] for p in pieces if p['role'] == 'internal_petticoat'
                or p['role'].startswith('foundation_petticoat')
                or (p['role'] == 'internal_photographic_lace'
                    and p['name'].startswith(('01 / ivory scalloped floral lace',
                                             '01 / black floral lace tier')))}
    if component_group != 'corset':
        raise ValueError('Unknown foundation component group.')
    return {p['name'] for p in pieces
            if p['role'] in {'boned_foundation_corset', 'corset_structural_detail'}
            or p['role'].startswith('foundation_corset')
            or (p['role'] == 'internal_photographic_lace'
                and p['name'].startswith('01 / corset /'))}
