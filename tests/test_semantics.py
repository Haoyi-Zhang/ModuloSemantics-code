"""Deterministic specification, boundary, and regression tests (stdlib unittest)."""
import itertools,json,unittest
from copy import deepcopy
from pathlib import Path
from semantic_certificates.builders import *
from semantic_certificates.checker import check
from semantic_certificates.logic import TruthTable,FormatError
from semantic_certificates.reference import run_source,operation,SourceFault
from semantic_certificates.target import run_target,primitive,Token
from semantic_certificates.resource_oracle import exhaustive_peak

ROOT=Path(__file__).resolve().parents[1]
def same(x,y):return json.dumps(x,sort_keys=True)==json.dumps(y,sort_keys=True)

class SemanticsTests(unittest.TestCase):
    def test_scalar_division_signs(self):
        for x,y,expected in [(7,3,2),(-7,3,-2),(7,-3,-2),(-7,-3,2),(0,-3,0)]:
            self.assertEqual(operation('div',[x,y]),expected)
            self.assertEqual(primitive('div',[x,y]),expected)
        self.assertEqual(operation('div',[1,0]),SourceFault('division-by-zero'))
        self.assertEqual(primitive('div',[1,0]),Token('division-by-zero'))
    def test_memory_is_functional(self):
        original=(1,2)
        self.assertEqual(operation('store',[original,0,7]),(7,2))
        self.assertEqual(primitive('store',[original,0,7]),(7,2))
        self.assertEqual(original,(1,2))
        self.assertEqual(operation('load',[original,-1]),SourceFault('bounds'))
        self.assertEqual(primitive('load',[original,2]),Token('bounds'))
    def test_lifted_faults_are_distinct_from_values(self):
        self.assertEqual(operation('add',[SourceFault('bounds'),3]),SourceFault('bounds'))
        self.assertEqual(primitive('add',[Token('bounds'),3]),Token('bounds'))
    def test_predicate_bitsets(self):
        tt=TruthTable(['p','q']); full=tt.all
        self.assertEqual(tt.bits(disj('p',neg('p'))),full)
        self.assertEqual(tt.bits(conj('p',neg('p'))),0)
        self.assertEqual(tt.bits(neg(conj('p','q'))),full^tt.bits(conj('p','q')))
        with self.assertRaises(FormatError):tt.bits('undeclared')
    def test_catalogue_admission(self):
        for base in catalogue().values():
            for mode in ('wait','recover'):
                p=build(base,mode);self.assertTrue(check(p).accepted)
    def test_zero_trip_and_drain(self):
        p=build(catalogue()['guarded-division'])
        for n in (0,1,2,9,33):
            d=data_for(p,n,[bool(k%3) for k in range(2*n)],{'x':3,'y':2,'z':0})
            self.assertTrue(same(run_source(p,d),run_target(p,d)))
    def test_negative_initial_indices_and_nonzero_initials(self):
        p=build(catalogue()['recurrence-three'])
        for n in range(8):
            d=data_for(p,n,[True]*2*n,{'x':2})
            for k in d['initial']['s']:d['initial']['s'][k]=10+int(k)
            self.assertTrue(same(run_source(p,d),run_target(p,d)))
    def test_wrong_path_fault_is_not_observable(self):
        p=build(catalogue()['guarded-division'])
        d=data_for(p,1,(False,True),{'x':1,'y':0,'z':7})
        self.assertEqual(run_source(p,d)['status'],'done')
        self.assertTrue(same(run_source(p,d),run_target(p,d)))
        self.assertEqual(run_target(p,d,eager_faults=True)['status'],'fault')
    def test_precise_fault_prefix(self):
        p=build(catalogue()['fault-prefix'])
        d=data_for(p,1,(True,True),{'x':2,'y':0,'z':3})
        expected=[['emit',0,'a',3],['fault',0,'b','division-by-zero']]
        self.assertEqual(run_source(p,d)['trace'],expected)
        self.assertEqual(run_target(p,d)['trace'],expected)
        self.assertNotEqual(run_target(p,d,reverse_retirement=True)['trace'],expected)
    def test_opaque_identifier_regression(self):
        w=json.loads((ROOT/'cases/counterexamples/opaque-identifier.json').read_text())
        self.assertTrue(check(w['program']).accepted)
        self.assertTrue(same(run_source(w['program'],w['input']),run_target(w['program'],w['input'])))
    def test_false_activation_availability_regression(self):
        w=json.loads((ROOT/'cases/counterexamples/false-guard-release.json').read_text())
        verdict=check(w['program'])
        self.assertFalse(verdict.accepted)
        self.assertIn('guard_availability',[x['code'] for x in verdict.issues])
    def test_false_mux_choice_requires_available_atoms(self):
        p=build(make_program([instruction('a','id',[inp('x')])]),'recover')
        join=next(a for a in p['attempts'] if a['name']=='f_a_join')
        join['choices'].append({'when':['and','p',False],'attempt':'f_a_op'})
        self.assertFalse(check(p).accepted)
    def test_false_retirement_choice_requires_available_atoms(self):
        p=build(make_program([instruction('a','id',[inp('x')])],release=0),'wait')
        p['guard_ready']['p']=p['retire']+1
        p['retirement']['a'].append({'when':['and','p',False],'attempt':'w_a_op'})
        self.assertFalse(check(p).accepted)
    def test_retirement_reads_source_guards(self):
        p=build(catalogue()['identity-boundary'])
        p['guard_ready']['p']=p['retire']+1
        self.assertFalse(check(p).accepted)
    def test_bad_shape_fails_closed(self):
        malformed=[None,[],{}, {'ii':True}]
        p=build(catalogue()['guarded-division'])
        for field,value in [('ii',0),('ii',True),('attempts',[]),('nodes',[]),('retirement',{}),('actual',['p','p'])]:
            q=deepcopy(p);q[field]=value;malformed.append(q)
        q=deepcopy(p);q['attempts'][1]['name']=q['attempts'][0]['name'];malformed.append(q)
        q=deepcopy(p);q['nodes'][0]['args'][0]=node('r');malformed.append(q)
        for q in malformed:self.assertFalse(check(q).accepted)
    def test_shifted_complements_not_exclusive(self):
        p=make_program([instruction('a','id',[inp('x')])],release=0,capacity=1)
        p['predicted']=[];p['guard_ready']={'p':0};p['ii']=1;p['retire']=2
        p['attempts']=[{'name':'u','node':'a','kind':'op','when':'p','offset':0,'args':[inp('x')]},
                       {'name':'v','node':'a','kind':'op','when':neg('p'),'offset':1,'args':[inp('x')]}]
        p['retirement']={'a':[{'when':True,'attempt':'u'}]}
        rows=check(p).resources;self.assertEqual(rows[0]['peak'],2)
        oracle=exhaustive_peak(p,2);self.assertEqual(oracle['peaks'][('alu',0)],2)
    def test_same_stage_complements_are_exclusive(self):
        p=make_program([instruction('a','id',[inp('x')])],release=0,capacity=1)
        p['predicted']=[];p['guard_ready']={'p':0};p['ii']=1;p['retire']=1
        p['attempts']=[{'name':'u','node':'a','kind':'op','when':'p','offset':0,'args':[inp('x')]},
                       {'name':'v','node':'a','kind':'op','when':neg('p'),'offset':0,'args':[inp('x')]}]
        p['retirement']={'a':[{'when':'p','attempt':'u'},{'when':neg('p'),'attempt':'v'}]}
        self.assertTrue(check(p).accepted);self.assertEqual(check(p).resources[0]['peak'],1)
    def test_unknown_fields_are_not_silently_ignored(self):
        p=build(catalogue()['guarded-division']);p['guarantee']='trusted'
        self.assertFalse(check(p).accepted)

if __name__=='__main__':unittest.main()
