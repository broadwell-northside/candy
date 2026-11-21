"""ComfyUI 'UI' workflow (the normal Save) -> 'API' workflow. Needs ComfyUI's /object_info.
Used by the app for imported workflows and by tools/build_video_models.py."""
import json,os,sys
OI=None
def set_object_info(oi):
    global OI
    OI=oi
def _oi():
    global OI
    if OI is None:
        OI=json.load(open(os.environ.get('ES_OBJECT_INFO','/tmp/object_info.json')))
    return OI
WIDGET_TYPES={'INT','FLOAT','STRING','BOOLEAN','COMBO','COLOR','CURVE'}
def is_widget(s):
    t=s[0]; return isinstance(t,list) or t in WIDGET_TYPES or t=='COMFY_DYNAMICCOMBO_V3'
def consume(spec,wv,wi,connected,inputs,prefix=''):
    for name,s in spec.items():
        if not is_widget(s): continue
        opts=s[1] if len(s)>1 and isinstance(s[1],dict) else {}
        full=prefix+name
        val=wv[wi] if wi<len(wv) else opts.get('default'); wi+=1
        if wi<len(wv) and isinstance(wv[wi],str) and wv[wi] in('fixed','randomize','increment','decrement') and (opts.get('control_after_generate') or name in('seed','noise_seed')):
            wi+=1
        if full not in connected and val is not None: inputs[full]=val
        if s[0]=='COMFY_DYNAMICCOMBO_V3':
            for o in opts['options']:
                if o['key']==val:
                    sub={**o['inputs'].get('required',{}),**o['inputs'].get('optional',{})}
                    wi=consume(sub,wv,wi,connected,inputs,full+'.')
    return wi
BYPASSED=[]
def convert(ui, overrides=None):
    BYPASSED.clear()
    if ui.get('definitions',{}).get('subgraphs'):
        ui=flatten(ui)
    nodes={n['id']:n for n in ui['nodes']}
    links={l[0]:l for l in ui['links']}
    api={}
    for nid,n in nodes.items():
        t=n['type']
        if t in('Reroute','Note','MarkdownNote') or n.get('mode')==2: continue
        if n.get('mode')==4: BYPASSED.append(str(nid))
        if t not in _oi(): raise ValueError(f"This workflow uses a node ComfyUI doesn't have: {t}. Install that custom node in ComfyUI first.")
        info=_oi()[t]; spec={**info['input'].get('required',{}),**info['input'].get('optional',{})}
        connected={i['name']:i['link'] for i in n.get('inputs',[]) if i.get('link') is not None}
        wv=n.get('widgets_values') or []
        if isinstance(wv,dict): wv=[]
        inputs={}
        consume(spec,list(wv),0,connected,inputs)
        for name,lid in connected.items():
            l=links[lid]; inputs[name]=[str(l[1]),l[2]]
        api[str(nid)]={'class_type':t,'inputs':inputs,'_meta':{'title':n.get('title') or t}}
    if BYPASSED: bypass(api,[b for b in BYPASSED if b in api])
    return api
def bypass(api, ids_passthrough):
    """replace refs to passthrough nodes (output i == input) with their input"""
    for pid in ids_passthrough:
        n=api.pop(pid); srcs=[v for v in n['inputs'].values() if isinstance(v,list)]
        for m in api.values():
            for k,v in list(m['inputs'].items()):
                if isinstance(v,list) and v[0]==pid:
                    if srcs: m['inputs'][k]=srcs[0]
                    else: del m['inputs'][k]   # bypassed source with no input: the optional input is just left empty
def resolve_switch(api, sid, which):
    n=api.pop(sid); src=n['inputs'][which]
    for m in api.values():
        for k,v in m['inputs'].items():
            if isinstance(v,list) and v[0]==sid: m['inputs'][k]=src
def prune(api, keep_outputs):
    need=set(); stack=list(keep_outputs)
    while stack:
        i=stack.pop()
        if i in need: continue
        need.add(i)
        for v in api[i]['inputs'].values():
            if isinstance(v,list): stack.append(v[0])
    return {k:v for k,v in api.items() if k in need}

def flatten(ui):
    """inline subgraphs into a flat UI graph (links as lists)."""
    sgs={sg['id']:sg for sg in ui.get('definitions',{}).get('subgraphs',[])}
    def L(l): return l if isinstance(l,list) else [l['id'],l['origin_id'],l['origin_slot'],l['target_id'],l['target_slot'],l.get('type')]
    nodes=[dict(n) for n in ui['nodes']]; links=[L(l) for l in ui['links']]
    changed=True; nid_counter=[100000]; lid_counter=[900000]
    while changed:
        changed=False
        for n in list(nodes):
            if n['type'] not in sgs: continue
            changed=True; sg=sgs[n['type']]; nodes.remove(n)
            idmap={}
            for sn in sg['nodes']:
                nid_counter[0]+=1; idmap[sn['id']]=nid_counter[0]
                c=json.loads(json.dumps(sn)); c['id']=idmap[sn['id']]; nodes.append(c)
            inner=[L(l) for l in sg['links']]
            # outer links into this subgraph node: target_id==n.id, target_slot = subgraph input index
            outer_in={l[4]:l for l in links if l[3]==n['id']}
            outer_out=[l for l in links if l[1]==n['id']]
            links=[l for l in links if l[3]!=n['id'] and l[1]!=n['id']]
            new=[]
            for l in inner:
                o,os_,t,ts=l[1],l[2],l[3],l[4]
                if o==-10:
                    if os_ not in outer_in: continue
                    src=outer_in[os_]; o,os_=src[1],src[2]
                else: o=idmap[o]
                if t==-20:
                    for ol in outer_out:
                        if ol[2]==ts:
                            lid_counter[0]+=1; new.append([lid_counter[0],o,os_,ol[3],ol[4],l[5]])
                    continue
                t=idmap[t]
                lid_counter[0]+=1; new.append([lid_counter[0],o,os_,t,ts,l[5]])
            # remap link ids in node inputs
            links+=new
        # rebuild node input link ids from links list
    byid={n['id']:n for n in nodes}
    for n in nodes:
        for i in n.get('inputs',[]) or []: i['link']=None
        for o in n.get('outputs',[]) or []: o['links']=[]
    for l in links:
        t=byid.get(l[3]); 
        if t is None: continue
        ins=t.get('inputs') or []
        if l[4] < len(ins): ins[l[4]]['link']=l[0]
    return {'nodes':nodes,'links':links}
