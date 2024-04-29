from typing import Dict

from pydantic import BaseModel,ValidationError,create_model
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from models import Entry,Many_Entries
from mongodb import entries_db,match_db
from schemas.helpers import get_schema

cached_models = {}

entry_types = ['match','pit']

def verify_entry(entry : Entry, team : int):
    if team not in cached_models.keys():
        cache_model(team)
    try:
        cached_models[team](**entry.model_dump())
    except ValidationError:
        return False
    if entry.metadata["type"] not in entry_types:
        return False
    return True

def add_entry(entry : Entry, team : int):
    db = entries_db[entry.metadata["type"]]
    db.insert_one(entry.model_dump())

def add_many_entries(entries : Many_Entries, team : int):
    db = entries_db[entries.entries[0].metadata["type"]]
    uploadable_data = jsonable_encoder(entries)
    db.insert_many(uploadable_data['entries'])

def delete_entries(team : int, query : dict):
    #query['metadata.scouter.team'] = team
    match_db.delete_many(query)

def get_entries(team : int, query : dict) -> dict:
    cursor = match_db.find(query,{"_id" : 0})
    re = [x for x in cursor]
    filtered = list(filter(lambda x: x['metadata']['scouter']['team'] == team or x['metadata']['public'] is True,re))
    return {'entries' : filtered}

def get_entries_new(team : int, query : list) -> dict:
    cursor = match_db.find({}, {"_id" : 0})
    re = [x for x in cursor]
    # TO-DO: permissions
    filtered = []
    for entry in re:
        for q in query:
            f, v = q
            if find_by_key(entry, f) != v:
                break
        else:
            filtered.append(entry)
    return {'entries' : filtered}


def filter_access(team : int, entries_list : list) -> bool:
    for x in entries_list:
        if x['metadata']['scouter']['team'] == team:
            return True
        if 'sharedWith' in x['metadata']:
            for sharedWithTeam in x['metadata']['sharedWith']:
                if sharedWithTeam == team:
                    return True
    return False


def find_by_key(x: dict, key: str):
    key = key.split('.')
    try:
        for k in key:
            x = x[k]
        return x
    except:
        raise HTTPException(422, detail="Invalid query")
    

def convert_type(entry):
    if isinstance(entry,dict):
        convert_schema(entry)
    if entry == 'int':
        return (int,...)
    elif entry == 'str':
        return (str,...)
    elif entry == 'bool':
        return (bool,...)
    else:
        return (type(entry),entry)    

def convert_schema(schema : dict) -> dict:
    new_schema = {}
    for k,v in schema.items():
        new_schema[k] = convert_type(v)
    return new_schema

def cache_model(team : int):
    schema_types = ['metadata','abilities','counters','data','ratings','timers']
    models : Dict[str,BaseModel] = {}
    for type in schema_types:
        schema = get_schema(team,type)
        del schema["schema_type"]
        models[type] = create_model(f'{type}_model',**convert_schema(schema))
    
    class Model(BaseModel):
        metadata : models['metadata']  # type: ignore # noqa: F821
        abilities : models['abilities']  # type: ignore # noqa: F821
        counters : models['counters']  # type: ignore # noqa: F821
        data : models['data']  # type: ignore # noqa: F821
        ratings : models['ratings']  # type: ignore # noqa: F821
        timers : models['timers']  # type: ignore # noqa: F821

    cached_models[team] = Model

def cache_model_new(team: int):
    cached_models[team] = create_model(f'{team}_data_model', ) ## finish