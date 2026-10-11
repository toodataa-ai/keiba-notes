#!/usr/bin/env python3
"""v2 presentation-only: extract additional COMPLETE purchasable wheels/multis.
Keep v1 report renderer, immutable CSS, official final_bets and proof untouched.
Original JRA purchase command verifier independently matches all displayed sets.
"""
import importlib.util
from itertools import combinations, permutations
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('immutable_jra_purchase_overlay_v1',HERE/'jra-pdf-presentation-overlay-v1.py')
old=importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
v1_derived=old._display_only_group_candidates

def maximal_cliques(nodes,edges,max_horses=6):
    """Small deterministic maximal complete graphs; no illegal partial wheel."""
    nodes=sorted(set(nodes))
    observed=set()
    result=[]
    for seed in nodes:
        members=[seed]
        for h in nodes:
            if h in members or len(members)>=max_horses:continue
            if all(tuple(sorted((h,x))) in edges for x in members):
                members.append(h)
        if len(members)>=3:
            k=tuple(members)
            if k not in observed:result.append(k);observed.add(k)
    return result

def extra_derived(final_by_key):
    by_type_stake={}
    for key,line in final_by_key.items():
        by_type_stake.setdefault((key[0],line['stake_yen']),set()).add(key)
    created=[]
    dedupe=set()
    def offer(typ,mode,definition,lines,available,unit):
        keys={old.bet_key({'type':typ,'selection':list(xs)}) for xs in lines}
        if len(keys)<2 or not keys.issubset(available):
            return
        signature=(typ,unit,tuple(sorted(keys)),mode)
        if signature in dedupe:return
        st={'strategy_id':'DISPLAY_V2_'+str(len(created)+1)+'_'+typ+'_'+mode+'_'+str(unit),
            'type':typ,'strategy_kind':mode,'definition':definition,
            'lines':[{'type':typ,'selection':list(k[1])} for k in sorted(keys)]}
        if not old._strategy_lines_match_definition(st,keys):
            raise ValueError('JRA presentation v2 blocker: derived group re-expansion differs from purchased lines')
        created.append(st);dedupe.add(signature)
    for (typ,unit),available in by_type_stake.items():
        nums=sorted({h for _,sel in available for h in sel})
        if typ in ('馬連','ワイド','枠連'):
            for axis in nums:
                others=[p for p in nums if p!=axis and
                        old.bet_key({'type':typ,'selection':[axis,p]}) in available]
                if len(others)>=2:
                    offer(typ,'key_wheel',{'key':axis,'partners':others},
                          [[axis,p] for p in others],available,unit)
        if typ=='馬単':
            for axis in nums:
                first=[p for p in nums if p!=axis and (typ,(axis,p)) in available]
                second=[p for p in nums if p!=axis and (typ,(p,axis)) in available]
                common=sorted(set(first)&set(second))
                for mode,partners,raw in [
                    ('key_wheel_first',first,[[axis,p] for p in first]),
                    ('key_wheel_second',second,[[p,axis] for p in second]),
                    ('key_wheel_multi',common,[[axis,p] for p in common]+[[p,axis] for p in common])]:
                    if len(partners)>=2:
                        offer(typ,mode,{'key':axis,'partners':partners},raw,available,unit)
        if typ=='三連複':
            for a,b in combinations(nums,2):
                partners=[p for p in nums if p not in (a,b) and
                          old.bet_key({'type':typ,'selection':[a,b,p]}) in available]
                if len(partners)>=2:
                    offer(typ,'two_key_wheel',{'axes':[a,b],'partners':partners},
                          [[a,b,p] for p in partners],available,unit)
            for axis in nums:
                graph=set()
                for a,b in combinations([x for x in nums if x!=axis],2):
                    if old.bet_key({'type':typ,'selection':[axis,a,b]}) in available:
                        graph.add((a,b))
                for partner_set in maximal_cliques([x for x in nums if x!=axis],graph):
                    offer(typ,'one_key_wheel',{'key':axis,'partners':list(partner_set)},
                          [[axis,a,b] for a,b in combinations(partner_set,2)],available,unit)
        if typ=='三連単':
            for a,b in combinations(nums,2):
                for axes in ((a,b),(b,a)):
                    for positions in ((1,2),(1,3),(2,3)):
                        partners=[];raw=[]
                        for p in nums:
                            if p in axes:continue
                            row=[None,None,None]
                            row[positions[0]-1]=axes[0];row[positions[1]-1]=axes[1]
                            row[row.index(None)]=p
                            if (typ,tuple(row)) in available:
                                partners.append(p);raw.append(row)
                        if len(partners)>=2:
                            offer(typ,'two_key_fixed',{'axes':list(axes),'positions':list(positions),
                              'partners':partners},raw,available,unit)
                partners=[p for p in nums if p not in (a,b) and
                          all((typ,tuple(x)) in available for x in permutations([a,b,p]))]
                if len(partners)>=2:
                    raw=[list(x) for p in partners for x in permutations([a,b,p])]
                    offer(typ,'two_key_multi',{'axes':[a,b],'partners':partners},raw,available,unit)
            for axis in nums:
                remaining=[x for x in nums if x!=axis]
                for mode in ('one_key_fixed','one_key_multi'):
                    for position in ((1,2,3) if mode=='one_key_fixed' else (1,)):
                        graph=set()
                        for a,b in combinations(remaining,2):
                            triples=[list(x) for x in permutations([axis,a,b]) if
                                mode=='one_key_multi' or x[position-1]==axis]
                            if triples and all((typ,tuple(t)) in available for t in triples):
                                graph.add((a,b))
                        for partner_set in maximal_cliques(remaining,graph):
                            raw=[list(x) for a,b in combinations(partner_set,2)
                                 for x in permutations([axis,a,b]) if
                                 mode=='one_key_multi' or x[position-1]==axis]
                            definition={'key':axis,'partners':list(partner_set)}
                            if mode=='one_key_fixed':definition['position']=position
                            offer(typ,mode,definition,raw,available,unit)
    return created

def better_derived(final_by_key):
    base=v1_derived(final_by_key)
    extra=extra_derived(final_by_key)
    # All candidate groups are merely suggestions; v1 purchase_commands verifies
    # that every accepted group is complete, fixed-price, disjoint and sum-preserving.
    return base+extra

old._display_only_group_candidates=better_derived
if __name__=='__main__':
    old.main()
