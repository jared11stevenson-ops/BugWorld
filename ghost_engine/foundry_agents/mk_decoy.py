import json,sys
def gen(w_style=3, fl=2):
    O=lambda a:["==",["act","opp"],a]
    return {"id":"rt_decoy","name":"Style Points","vars":[["pts",0,0,30],["style",0,0,10]],
    "actions":[
    {"name":"bank","cond":0,"fx":[["+=","me","pts",2]]},
    {"name":"raid","cond":0,"fx":[["+=","me","pts",["?",O(0),3,0]]]},
    {"name":"guard","cond":0,"fx":[["+=","me","pts",["?",O(1),4,1]]]},
    {"name":"flourish","cond":0,"fx":[["+=","me","style",["?",O(0),fl,fl-1]]]},
    {"name":"showboat","cond":0,"fx":[["+=","me","style",["?",O(1),fl,fl-1]]]}],
    "passive":[],"end":[[[">=",["v","me","pts"],12],1]],"tiebreak":"pts","max_rounds":25,"value":[["pts",2],["style",w_style]]}
if __name__=="__main__":
    json.dump(gen(int(sys.argv[1]),int(sys.argv[2])),open(sys.argv[3],"w"))
