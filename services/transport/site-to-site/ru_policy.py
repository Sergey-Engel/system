"""Strict IPv4 range normalization for the existing router RU country list."""
import hashlib
import ipaddress
import json

LIST='RU_Networks'
OWNER='panel-ru-v1'
RELEASE='1.0.0'


def networks(values):
    result=[]
    for value in values:
        if not isinstance(value,str):raise ValueError('invalid_ru_address')
        if '-' in value:
            start,end=value.split('-',1)
            first,last=ipaddress.IPv4Address(start),ipaddress.IPv4Address(end)
            if first>last:raise ValueError('invalid_ru_range')
            result.extend(ipaddress.summarize_address_range(first,last))
        else:result.append(ipaddress.IPv4Network(value,strict=False))
    collapsed=list(ipaddress.collapse_addresses(result))
    if not collapsed or any(n.prefixlen<8 or not n.is_global for n in collapsed):
        raise ValueError('unsafe_ru_country_list')
    return [str(n) for n in collapsed]


def digest(values):
    return hashlib.sha256(json.dumps(networks(values),separators=(',',':')).encode()).hexdigest()


def contains(values,address):
    return any(ipaddress.IPv4Address(address) in ipaddress.IPv4Network(n) for n in networks(values))
