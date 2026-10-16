"""GUC promotion policy supplied by the owner; configurable timing assumptions."""
DAY=86400
# Lowest to highest. Emperor is the Discord server owner, outside this ladder.
RANKS=[
('recruit','Recruit','enlisted',0,None),
('pvt','Private','enlisted',5,None),
('psc','Private Second Class','enlisted',10,None),
('pfc','Private First Class','enlisted',15,None),
('spc','Specialist','enlisted',20,None),
('cpl','Corporal','enlisted',25,None),
('sgt','Sergeant','enlisted',30,None),
('ssg','Staff Sergeant','enlisted',35,None),
('sfc','Sergeant First Class','nco',None,'leadership and combat skills'),
('msg','Master Sergeant','nco',None,'leadership and combat skills'),
('1sg','First Sergeant','nco',None,'good leadership and good combat skills'),
('sgm','Sergeant Major','nco',None,'good leadership and good combat skills'),
('csm','Command Sergeant Major','nco',None,'amazing leadership and amazing combat skills'),
('sme','Sergeant Major of the Era','nco',None,'amazing leadership and amazing combat skills'),
('wo','Warrant Officer','warrant',None,'respective commander approval'),
('cwo','Chief Warrant Officer','warrant',None,'respective commander approval'),
('hwo','High Warrant Officer','warrant',None,'respective commander approval'),
('cmwo','Command Warrant Officer','warrant',None,'respective commander approval'),
('cgwo','Commanding Warrant Officer','warrant',None,'respective commander approval'),
('2lt','Second Lieutenant','officer',None,'respective commander observed hosting combat'),
('1lt','First Lieutenant','officer',None,'leadership capability and mindset'),
('cpt','Captain','officer',None,'leadership capability and mindset'),
('maj','Major','officer',None,'leadership capability and mindset'),
('ltcol','Lieutenant Colonel','officer',None,'leadership capability and mindset'),
('col','Colonel','officer',None,'leadership capability and mindset'),
('bg','Brigadier General','high',None,'commander approval and Emperor-shadowed On-Duty'),
('ltg','Lieutenant General','high',None,'two distinct Commanders'),
('gen','General','high',None,'three distinct Commanders'),
('cmdr','Commander','high',None,'Emperor appointment only'),
('mc','Marshal Commander','high',None,'Emperor appointment only'),
('hc','High Commander','high',None,'Emperor appointment only')]
BY_CODE={r[0]:r for r in RANKS}
CODES=[r[0] for r in RANKS]
WAIT_DAYS={'enlisted':1,'nco':3,'warrant':6,'officer':6,'high':10}

def requirements(current,target,rank_since,service_since,marks,adult,now,jump=False,wait_days=None):
    """Return blocking reasons. Wait is based on destination tier (documented assumption)."""
    errors=[]
    if CODES.index(target)!=CODES.index(current)+1:errors.append('Promotion must advance exactly one rank.')
    tier=BY_CODE[target][2]
    days=3 if jump else (wait_days or WAIT_DAYS)[tier]
    due=rank_since+days*DAY
    if now<due:errors.append(f'Wait until Unix time {int(due)} ({days} days in current rank).')
    needed=BY_CODE[target][3]
    if needed is not None and marks<needed:
        if not(target=='pvt' and now-service_since>=2*DAY):errors.append(f'Requires {needed} cumulative attendance marks; has {marks}.')
    if tier=='high' and not adult:errors.append('Owner must verify 18+ eligibility for High Command.')
    return errors

def approval_errors(target,commander_ids,co_ids,respective_id,votes,emperor_id):
    """votes=(approver_id,kind,evidence). Call with CURRENT verified authority IDs."""
    valid={(uid,kind) for uid,kind,evidence in votes if evidence.strip()}
    commanders={uid for uid,kind in valid if kind=='commander' and uid in commander_ids}
    sponsors={uid for uid,kind in valid if kind=='sponsor' and uid in co_ids}
    tier=BY_CODE[target][2]
    if target in ('hc','cmdr','mc'):
        return [] if (emperor_id,'emperor') in valid else ['Requires Emperor appointment approval.']
    if target in ('gen','ltg'):
        n=3 if target=='gen' else 2
        return [] if len(commanders)>=n else [f'Requires {n} distinct current Commanders; has {len(commanders)}.']
    errors=[]
    if tier in ('warrant','officer') or target=='bg':
        if respective_id not in commanders:errors.append('Requires approval from the assigned respective Commander.')
    if target=='2lt' and (respective_id,'combat_shadow') not in valid:
        errors.append('Requires respective Commander’s observed-combat assessment.')
    if target=='bg' and (emperor_id,'emperor_shadow') not in valid:
        errors.append('Requires Emperor’s On-Duty shadow assessment.')
    if tier=='nco' and not sponsors:errors.append('Requires a current same-era commissioned officer sponsor with skills evidence.')
    return errors
