#!/usr/bin/env python3
"""Authorship source for the final v1 benchmark. Refuses to rebuild after freeze."""
import difflib
import json
from pathlib import Path
import validate_final as v

HERE=Path(__file__).resolve().parent
ROWS=[]
CODE_RULES=(' No imports, example calls, global/nonlocal declarations or dunder/reflection access. '
            'Do not mutate inputs unless explicitly requested. Available builtins: '+', '.join(v.SAFE_BUILTINS)+'.')
CODE_CONTRACT=' Return only raw Python function definitions; no prose or Markdown fences.'+CODE_RULES

def case(fn,args,want):
    return {'function':fn,'args':args,'expected':want,'unchanged_args':True}

def return_contract(samples):
    names={bool:'bool',int:'int',str:'str',list:'list',dict:'dict',float:'float',type(None):'None'}
    types={fn:names[type(want)] for fn,args,want in samples}
    return ' Required return types: '+', '.join(fn+' -> '+kind for fn,kind in types.items())+'. List results (including nested lists) must be lists, not tuples; integer results must be int, not float or bool.'

def code(category, family, description, answer, samples, broken=None):
    prompt=description+return_contract(samples)+CODE_CONTRACT
    if broken: prompt+='\nCurrent code:\n'+broken
    if category=='Test-driven fixing':
        prompt+='\nTests (arguments -> expected JSON-compatible result):\n'+json.dumps(samples)
    ROWS.append({'id':'v1_'+family,'family':family,'category':category,'response_mode':'python_code',
                 'prompt':prompt,'reference':answer+'\n','cases':[case(fn,args,want) for fn,args,want in samples]})

def structured(category,family,snippet_or_files,output,tag,reason_text):
    mode='explanation_json' if category=='Code explanation' else 'repository_reasoning_json'
    task={'id':'v1_'+family,'family':family,'category':category,'response_mode':mode,
          'expected':{'output':output,'reason':tag}}
    if mode=='explanation_json':
        task['snippet']=snippet_or_files
        body='Trace this program:\n'+snippet_or_files
    else:
        task['files']=snippet_or_files;task['entry']='launch_v1.py'
        body='These virtual files share a directory. Run launch_v1.py:\n'+'\n'.join(name+':\n'+content for name,content in snippet_or_files.items())
    typ=('array' if isinstance(output,list) else 'object' if isinstance(output,dict) else 'boolean' if isinstance(output,bool) else 'integer' if isinstance(output,int) else 'string')
    task['prompt']=body+f'\nReturn one bare JSON object with exactly output ({typ}, the JSON value printed) and reason (string). No extra keys, prose or Markdown fences. The reason must equal "{tag}", meaning: {reason_text}. JSON whitespace and key order do not matter.'
    task['reference']=json.dumps(task['expected'],separators=(',',':'))
    ROWS.append(task)

def patch(family,goal,path,old,new,samples,context=2):
    ROWS.append({'id':'v1_'+family,'family':family,'category':'Patch generation','response_mode':'unified_diff',
        'prompt':f'Edit {path}. {goal} Preserve v1_untouched exactly. Return only a raw single-file unified diff with --- a/{path} and +++ b/{path} headers and valid @@ hunk counts. No prose or Markdown fences. CRLF transport and one extra terminal blank line are accepted; content indentation and trailing spaces must be preserved.'+return_contract(samples)+' The resulting file may contain only function definitions and comments.'+CODE_RULES+'\nCurrent file:\n'+old,
        'path':path,'source':old,'reference':''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path,n=context)),
        'preserve_functions':['v1_untouched'],'cases':[case(fn,args,want) for fn,args,want in samples]+[case('v1_untouched',[13],13)]})

def author():
    code('Simple coding','polynomial_fold',
        'Implement polynomial_at(coefficients,x). Coefficients are integers in highest-degree-first order. Return the integer polynomial value; no coefficients means zero.',
        'def polynomial_at(coefficients,x):\n    value=0\n    for coefficient in coefficients:\n        value=value*x+coefficient\n    return value',
        [('polynomial_at',[[2,-3,5],4],25),('polynomial_at',[[],7],0),('polynomial_at',[[8],-9],8),('polynomial_at',[[1,0,0],-3],9),('polynomial_at',[[4,2,-6],0],-6)])
    code('Simple coding','backspace_buffer',
        "Implement edited_text(events). Each '#' deletes the most recent surviving character if any; all other characters append literally. Return the final string.",
        "def edited_text(events):\n    buffer=[]\n    for char in events:\n        if char=='#':\n            if buffer: buffer.pop()\n        else: buffer.append(char)\n    return ''.join(buffer)",
        [('edited_text',['ab#c##d'],'d'),('edited_text',['###'],'') ,('edited_text',['a b#c'],'a c'),('edited_text',['go##new'],'new'),('edited_text',[''],'')])
    code('Simple coding','nested_leaf_addresses',
        'Implement leaf_addresses(tree) for a nested dictionary with string keys and integer leaves. Return a list of [path,value] pairs, where path is a list of key strings. Visit keys in sorted order at every level; empty dictionaries contribute nothing.',
        'def leaf_addresses(tree):\n    result=[]\n    def visit(node,path):\n        if isinstance(node,dict):\n            for key in sorted(node): visit(node[key],path+[key])\n        else: result.append([path,node])\n    visit(tree,[])\n    return result',
        [('leaf_addresses',[{'z':3,'a':{'b':8,'a':2}}],[[['a','a'],2],[['a','b'],8],[['z'],3]]),('leaf_addresses',[{}],[]),('leaf_addresses',[{'x':{},'y':-1}],[[['y'],-1]])])
    code('Simple coding','cartesian_choices',
        'Implement choice_rows(groups), a list of integer lists. Return all choice combinations as lists, choosing one item per group, in nested-loop order (leftmost choice changes slowest). No groups has one empty combination; any empty group yields none.',
        'def choice_rows(groups):\n    rows=[[]]\n    for group in groups:\n        rows=[row+[item] for row in rows for item in group]\n    return rows',
        [('choice_rows',[[[2,7],[4,9]]],[[2,4],[2,9],[7,4],[7,9]]),('choice_rows',[[]],[[]]),('choice_rows',[[[1],[]]],[]),('choice_rows',[[[3],[5],[8,6]]],[[3,5,8],[3,5,6]])])
    code('Simple coding','decimal_carry_arrays',
        'Implement add_digit_arrays(left,right). Inputs are nonempty lists of decimal digits, most significant first, with no leading zeros except [0]. Return their sum as a digit list with the same convention.',
        'def add_digit_arrays(left,right):\n    i,j=len(left)-1,len(right)-1\n    carry=0\n    out=[]\n    while i>=0 or j>=0 or carry:\n        total=carry+(left[i] if i>=0 else 0)+(right[j] if j>=0 else 0)\n        out.append(total%10)\n        carry=total//10\n        i-=1\n        j-=1\n    return out[::-1]',
        [('add_digit_arrays',[[9,9],[1]],[1,0,0]),('add_digit_arrays',[[0],[0]],[0]),('add_digit_arrays',[[4,2],[5,7]],[9,9]),('add_digit_arrays',[[1],[9,9,9]],[1,0,0,0])])
    code('Simple coding','capacity_batching',
        'Implement capacity_batches(items,capacity). Items are strings each of length at most positive capacity. Greedily place consecutive strings in the current batch while their total length fits, otherwise start a new batch. Return list of string lists, no empty batches; empty input gives [].',
        'def capacity_batches(items,capacity):\n    out=[]\n    batch=[]\n    used=0\n    for item in items:\n        if batch and used+len(item)>capacity:\n            out.append(batch)\n            batch=[]\n            used=0\n        batch.append(item)\n        used+=len(item)\n    if batch: out.append(batch)\n    return out',
        [('capacity_batches',[['ab','c','de','f'],3],[['ab','c'],['de','f']]),('capacity_batches',[[],4],[]),('capacity_batches',[['','abc',''],3],[['','abc','']]),('capacity_batches',[['xy','z','w'],2],[['xy'],['z','w']])])

    code('Bug fixing','breadth_first_distance',
        'Fix hop_distance(graph,start,goal): directed graph maps string nodes to neighbor lists. Return minimum edge count or -1 if unreachable; missing nodes have no outgoing edges. Cycles are possible.',
        'def hop_distance(graph,start,goal):\n    queue=[(start,0)]\n    seen={start}\n    for node,distance in queue:\n        if node==goal: return distance\n        for neighbor in graph.get(node,[]):\n            if neighbor not in seen:\n                seen.add(neighbor)\n                queue.append((neighbor,distance+1))\n    return -1',
        [('hop_distance',[{'s':['a','b'],'a':['c'],'b':['g'],'c':['g']},'s','g'],2),('hop_distance',[{'a':['a']},'a','z'],-1),('hop_distance',[{},'x','x'],0),('hop_distance',[{'x':['y'],'y':['z']},'x','z'],2)],
        'def hop_distance(graph,start,goal):\n    stack=[(start,0)]\n    while stack:\n        node,distance=stack.pop()\n        if node==goal: return distance\n        for neighbor in graph.get(node,[]): stack.append((neighbor,distance+1))\n    return -1')
    code('Bug fixing','independent_grid_rows',
        'Fix reserved_grid(rows,columns,positions): return a rows-by-columns integer grid of zeros with specified [row,column] positions set to 1. Marking one row must not alter another. Positions are valid.',
        'def reserved_grid(rows,columns,positions):\n    grid=[[0]*columns for _ in range(rows)]\n    for row,column in positions: grid[row][column]=1\n    return grid',
        [('reserved_grid',[3,2,[[1,0]]],[[0,0],[1,0],[0,0]]),('reserved_grid',[1,3,[[0,2],[0,2]]],[[0,0,1]]),('reserved_grid',[0,2,[]],[]),('reserved_grid',[2,0,[]],[[],[]])],
        'def reserved_grid(rows,columns,positions):\n    grid=[[0]*columns]*rows\n    for row,column in positions: grid[row][column]=1\n    return grid')
    code('Bug fixing','overlapping_occurrences',
        'Fix match_offsets(text,needle) to return all starting indices of occurrences, including overlaps and a match ending at the final character. Needle is nonempty.',
        'def match_offsets(text,needle):\n    return [i for i in range(len(text)-len(needle)+1) if text[i:i+len(needle)]==needle]',
        [('match_offsets',['aaaa','aa'],[0,1,2]),('match_offsets',['end','end'],[0]),('match_offsets',['short','longer'],[]),('match_offsets',['ababa','aba'],[0,2]),('match_offsets',['','x'],[])],
        'def match_offsets(text,needle):\n    result=[]\n    index=0\n    while index<len(text)-len(needle):\n        if text[index:index+len(needle)]==needle:\n            result.append(index)\n            index+=len(needle)\n        else: index+=1\n    return result')
    code('Bug fixing','boolean_integer_boundary',
        'Fix integer_summary(items): return [count,total] for entries whose exact Python type is int. Booleans, floats, strings and None must be ignored.',
        'def integer_summary(items):\n    values=[item for item in items if type(item) is int]\n    return [len(values),sum(values)]',
        [('integer_summary',[[True,3,False,-2,4.0,'8',None]],[2,1]),('integer_summary',[[]],[0,0]),('integer_summary',[[0,7,9]],[3,16]),('integer_summary',[[True,False]],[0,0])],
        'def integer_summary(items):\n    values=[item for item in items if isinstance(item,int)]\n    return [len(values),sum(values)]')
    code('Bug fixing','identifier_full_scan',
        'Fix legal_token(text): nonempty ASCII identifiers begin with A-Z, a-z or underscore; later characters may also be digits. Return boolean. Any disallowed character makes the whole string invalid.',
        "def legal_token(text):\n    letters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'\n    return bool(text) and text[0] in letters and all(char in letters+'0123456789' for char in text[1:])",
        [('legal_token',['port_7'],True),('legal_token',['ab!'],False),('legal_token',['2ab'],False),('legal_token',['_'],True),('legal_token',[''],False),('legal_token',['aé'],False)],
        "def legal_token(text):\n    for char in text:\n        if char.isalnum() or char=='_': return True\n        return False\n    return True")
    code('Bug fixing','consecutive_alarm_state',
        'Fix alarm_streak(flags): return the longest consecutive run of true booleans. A false flag ends a run; empty input returns zero.',
        'def alarm_streak(flags):\n    current=best=0\n    for flag in flags:\n        current=current+1 if flag else 0\n        best=max(best,current)\n    return best',
        [('alarm_streak',[[True,True,False,True]],2),('alarm_streak',[[False,True,True,True]],3),('alarm_streak',[[]],0),('alarm_streak',[[False,False]],0),('alarm_streak',[[True,False,True,False,True]],1)],
        'def alarm_streak(flags):\n    current=best=0\n    for flag in flags:\n        if flag: current+=1\n        else: best=max(best,current)\n    return best')

    structured('Code explanation','nonlocal_counter_state',
        'import json\ndef new_counter():\n    total=6\n    def advance(step):\n        nonlocal total\n        total+=step\n        return total\n    return advance\nfirst=new_counter()\nsecond=new_counter()\nprint(json.dumps([first(2),first(-3),second(1)]))',
        [8,5,7],'separate_closures_retain_separate_state','each factory call owns a distinct captured counter')
    structured('Code explanation','nested_shallow_copy',
        "import json\noriginal={'queue':[4],'mode':'slow'}\nreplica=original.copy()\nreplica['queue'].append(8)\nreplica['mode']='fast'\nprint(json.dumps([original,replica]))",
        [{'queue':[4,8],'mode':'slow'},{'queue':[4,8],'mode':'fast'}],'outer_copy_shares_nested_queue','outer dictionaries differ while their nested list is shared')
    structured('Code explanation','eager_default_argument',
        "import json\ntrace=[]\ndef make_entry():\n    trace.append('made')\n    return 99\ncache={'hit':12}\na=cache.setdefault('hit',make_entry())\nb=cache.setdefault('miss',make_entry())\nprint(json.dumps([a,b,trace]))",
        [12,99,['made','made']],'arguments_evaluated_before_setdefault','the default-producing call runs even for an existing key')
    structured('Code explanation','exception_continue_accumulator',
        "import json\naccepted=[]\nerrors=0\nfor text in ['4','bad','-2','7']:\n    try:\n        number=int(text)\n    except ValueError:\n        errors+=1\n        continue\n    if number<0: continue\n    accepted.append(number*2)\nprint(json.dumps([accepted,errors]))",
        [[8,14],1],'handled_conversion_resumes_loop','invalid and negative entries skip later statements for that iteration')
    structured('Code explanation','lazy_source_mutation',
        'import json\nsource=[2,5,8]\nstream=(value*3 for value in source if value%2==0)\nsource[1]=4\nsource.append(10)\nprint(json.dumps(list(stream)))',
        [6,12,24,30],'generator_reads_source_when_consumed','the generator reads updated list entries during consumption')
    structured('Code explanation','assignment_rhs_snapshot',
        'import json\nvalues=[3,8,11]\nindex=0\nindex,values[index]=2,values[index]+5\nprint(json.dumps([index,values]))',
        [2,[3,8,8]],'rhs_first_then_targets_left_to_right','right-hand values are computed first and assignment targets then run left to right')

    helper='\ndef v1_untouched(value):\n    return value\n'
    patch('zigzag_integer_encoding','zigzag_number(n) encodes signed integers for a serializer: 0 maps to 0; positive n maps to 2*n; negative n maps to -2*n-1. Preserve distinct codes for opposite signs.','zigzag_v1.py',
        'def zigzag_number(n):\n    return 2*abs(n)\n'+helper,
        'def zigzag_number(n):\n    return 2*n if n>=0 else -2*n-1\n'+helper,
        [('zigzag_number',[0],0),('zigzag_number',[1],2),('zigzag_number',[-1],1),('zigzag_number',[3],6),('zigzag_number',[-3],5),('zigzag_number',[-100],199)])
    patch('switch_type_guard','switch_value(value) already handles strings yes/no. Insert handling of booleans before string methods, returning the boolean unchanged. Other inputs are strings.','switch_v1.py',
        "def switch_value(value):\n    word=value.lower()\n    return word=='yes'\n"+helper,
        "def switch_value(value):\n    if isinstance(value,bool):\n        return value\n    word=value.lower()\n    return word=='yes'\n"+helper,
        [('switch_value',[True],True),('switch_value',[False],False),('switch_value',['YES'],True),('switch_value',['no'],False)])
    patch('rook_conflict_scan','rook_conflict(board) returns whether any row or column of a rectangular string grid contains more than one R. A dot is empty. Do not stop scanning after a safe row; empty board returns False.','rooks_v1.py',
        "def rook_conflict(board):\n    for row in board:\n        if row.count('R')>1: return True\n        return False\n    for column in zip(*board):\n        if column.count('R')>1: return True\n    return False\n"+helper,
        "def rook_conflict(board):\n    for row in board:\n        if row.count('R')>1: return True\n    for column in zip(*board):\n        if column.count('R')>1: return True\n    return False\n"+helper,
        [('rook_conflict',[['R..','.RR']],True),('rook_conflict',[['R..','R..']],True),('rook_conflict',[['R..','.R.']],False),('rook_conflict',[[]],False)])
    old='def pack_fields(major,minor):\n    return (major<<4)|minor\n\ndef v1_untouched(value):\n    return value\n\ndef unpack_fields(value):\n    return [value>>4,value&15]\n'
    new='def pack_fields(major,minor):\n    return (major<<8)|minor\n\ndef v1_untouched(value):\n    return value\n\ndef unpack_fields(value):\n    return [value>>8,value&255]\n'
    patch('byte_field_roundtrip','Both fields occupy eight bits, not four. major/minor are 0..255. Correct both packing and unpacking; retain the middle helper.','fields_v1.py',old,new,
        [('pack_fields',[3,20],788),('unpack_fields',[788],[3,20]),('pack_fields',[255,255],65535),('unpack_fields',[256],[1,0])],context=1)
    patch('common_margin_removal','remove_margin(lines) removes the smallest leading-space count among nonblank lines from every line. Blank means only spaces; blank lines become empty. Preserve relative indentation and trailing spaces on nonblank lines. Inputs have no tabs/newlines.','margin_v1.py',
        'def remove_margin(lines):\n    return [line.strip() for line in lines]\n'+helper,
        "def remove_margin(lines):\n    widths=[len(line)-len(line.lstrip(' ')) for line in lines if line.strip(' ')]\n    width=min(widths) if widths else 0\n    return [line[width:] if line.strip(' ') else '' for line in lines]\n"+helper,
        [('remove_margin',[['  one  ','    two','  ']],['one  ','  two','']),('remove_margin',[['','   ']],['','']),('remove_margin',[['plain','  deeper']],['plain','  deeper'])])
    patch('visual_tab_stops','expand_stops(text,width) expands tabs to the NEXT multiple-of-width column, resetting the column after LF. Keep other characters unchanged; width is positive.','tabs_v1.py',
        "def expand_stops(text,width):\n    return text.replace('\\t',' '*width)\n"+helper,
        "def expand_stops(text,width):\n    out=[]\n    column=0\n    for char in text:\n        if char=='\\t':\n            spaces=width-column%width\n            out.append(' '*spaces)\n            column+=spaces\n        else:\n            out.append(char)\n            column=0 if char=='\\n' else column+1\n    return ''.join(out)\n"+helper,
        [('expand_stops',['a\tb',4],'a   b'),('expand_stops',['abcd\tX',4],'abcd    X'),('expand_stops',['xx\nq\t',3],'xx\nq  '),('expand_stops',['',2],'')])

    code('Multi-step debugging','uptime_event_pipeline',
        'Fix both functions. decode_edges(rows) converts strings "time:on"/"time:off" into [integer_time,boolean_on] pairs. active_seconds(rows) sums completed on/off intervals. Rows are chronological, start on, alternate, end off; empty is valid. Check decoded states and final durations.',
        "def decode_edges(rows):\n    return [[int(row.split(':')[0]),row.split(':')[1]=='on'] for row in rows]\ndef active_seconds(rows):\n    total=0\n    started=0\n    for time,on in decode_edges(rows):\n        if on: started=time\n        else: total+=time-started\n    return total",
        [('decode_edges',[['2:on','9:off']],[[2,True],[9,False]]),('active_seconds',[['2:on','9:off','12:on','16:off']],11),('active_seconds',[[]],0),('active_seconds',[['0:on','0:off']],0)],
        "def decode_edges(rows):\n    return [[row.split(':')[0],bool(row.split(':')[1])] for row in rows]\ndef active_seconds(rows):\n    total=0\n    for time,on in decode_edges(rows):\n        if on: started=time\n        else: total=time-started\n    return total")
    code('Multi-step debugging','rational_addition_pipeline',
        'Fix both functions. reduce_pair(n,d) returns [numerator,denominator] in lowest terms with positive denominator; d is nonzero. add_pairs(a,b) adds two such rational pairs and reduces the result. Zero must become [0,1].',
        'def reduce_pair(n,d):\n    x,y=abs(n),abs(d)\n    while y: x,y=y,x%y\n    n,d=n//x,d//x\n    return [-n,-d] if d<0 else [n,d]\ndef add_pairs(a,b):\n    return reduce_pair(a[0]*b[1]+b[0]*a[1],a[1]*b[1])',
        [('reduce_pair',[8,-12],[-2,3]),('reduce_pair',[0,-7],[0,1]),('add_pairs',[[1,3],[1,6]],[1,2]),('add_pairs',[[2,5],[-2,5]],[0,1]),('add_pairs',[[-1,2],[3,4]],[1,4])],
        'def reduce_pair(n,d):\n    return [n//d,1]\ndef add_pairs(a,b):\n    return reduce_pair(a[0]+b[0],a[1]+b[1])')
    code('Multi-step debugging','postfix_operand_pipeline',
        'Fix both functions. postfix_tokens(text) returns whitespace-separated tokens as integers or the strings +, -, *. postfix_value(text) evaluates valid postfix expressions, preserving left/right operand order. Inputs always produce exactly one value.',
        "def postfix_tokens(text):\n    return [token if token in ('+','-','*') else int(token) for token in text.split()]\ndef postfix_value(text):\n    stack=[]\n    for token in postfix_tokens(text):\n        if isinstance(token,int): stack.append(token)\n        else:\n            right=stack.pop()\n            left=stack.pop()\n            stack.append(left+right if token=='+' else left-right if token=='-' else left*right)\n    return stack[0]",
        [('postfix_tokens',['-3  8 +'],[-3,8,'+']),('postfix_value',['9 2 - 3 *'],21),('postfix_value',['2 9 -'],-7),('postfix_value',['-4'], -4),('postfix_value',['5 6 + 2 *'],22)],
        "def postfix_tokens(text):\n    return [int(t) if t.isdigit() else t for t in text.split(' ')]\ndef postfix_value(text):\n    stack=[]\n    for t in postfix_tokens(text):\n        if isinstance(t,int): stack.append(t)\n        else:\n            a,b=stack.pop(),stack.pop()\n            stack.append(a+b if t=='+' else a-b if t=='-' else a*b)\n    return stack[0]")
    code('Multi-step debugging','luhn_payload_pipeline',
        'Fix both functions. luhn_terms(payload) takes a nonempty digit string WITHOUT its check digit: from the right, double the rightmost payload digit and then every other digit; subtract 9 if a doubled value exceeds 9. Return terms in original left-to-right order. luhn_digit returns the single integer check digit making the sum a multiple of 10.',
        'def luhn_terms(payload):\n    out=[]\n    for i,char in enumerate(payload):\n        value=int(char)\n        if (len(payload)-i)%2==1:\n            value*=2\n            if value>9: value-=9\n        out.append(value)\n    return out\ndef luhn_digit(payload):\n    return (-sum(luhn_terms(payload)))%10',
        [('luhn_terms',['123'],[2,2,6]),('luhn_terms',['59'],[5,9]),('luhn_digit',['123'],0),('luhn_digit',['59'],6),('luhn_digit',['0'],0)],
        'def luhn_terms(payload):\n    return [int(c)*2 for c in payload]\ndef luhn_digit(payload):\n    return 10-sum(luhn_terms(payload))%10')
    code('Multi-step debugging','permission_bit_pipeline',
        'Fix both functions. permission_bits(names) maps read=1, write=2, execute=4 and combines using bitwise OR; duplicate names are harmless. includes_permissions(held,required) accepts lists of these names and returns true exactly when ALL required bits are held, including empty requirements.',
        "def permission_bits(names):\n    codes={'read':1,'write':2,'execute':4}\n    bits=0\n    for name in names: bits|=codes[name]\n    return bits\ndef includes_permissions(held,required):\n    need=permission_bits(required)\n    return permission_bits(held)&need==need",
        [('permission_bits',[['write','write','read']],3),('includes_permissions',[['read'],['read','write']],False),('includes_permissions',[[],[]],True),('includes_permissions',[['write','execute'],['execute']],True)],
        "def permission_bits(names):\n    codes={'read':1,'write':2,'execute':4}\n    return sum(codes[n] for n in names)\ndef includes_permissions(held,required):\n    return bool(permission_bits(held)&permission_bits(required))")
    code('Multi-step debugging','retry_delay_pipeline',
        'Fix both functions. retry_delays(base,cap,count) returns count delays: base, twice base, four times base, etc, each capped at cap. base/cap are positive; count nonnegative. retry_elapsed(base,cap,attempts,duration) includes one duration per attempt and a delay only BETWEEN attempts, never after the last.',
        'def retry_delays(base,cap,count):\n    out=[]\n    delay=base\n    for _ in range(count):\n        out.append(min(delay,cap))\n        delay*=2\n    return out\ndef retry_elapsed(base,cap,attempts,duration):\n    return attempts*duration+sum(retry_delays(base,cap,max(0,attempts-1)))',
        [('retry_delays',[3,8,4],[3,6,8,8]),('retry_elapsed',[3,8,4,2],25),('retry_elapsed',[3,8,1,2],2),('retry_elapsed',[3,8,0,2],0),('retry_delays',[9,4,2],[4,4])],
        'def retry_delays(base,cap,count):\n    return [max(base*i,cap) for i in range(count)]\ndef retry_elapsed(base,cap,attempts,duration):\n    return duration+sum(retry_delays(base,cap,attempts))')

    code('Test-driven fixing','edit_distance_table',
        'Implement edit_cost(left,right): minimum number of single-character insertions, deletions or replacements needed to transform left into right, each costing 1. Matching costs zero. Strings are short.',
        'def edit_cost(left,right):\n    previous=list(range(len(right)+1))\n    for i,a in enumerate(left,1):\n        current=[i]\n        for j,b in enumerate(right,1):\n            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))\n        previous=current\n    return previous[-1]',
        [('edit_cost',['kitten','sitting'],3),('edit_cost',['','four'],4),('edit_cost',['same','same'],0),('edit_cost',['ab','ba'],2),('edit_cost',['abc','ac'],1)])
    code('Test-driven fixing','dependency_schedule',
        'Implement schedule_units(dependencies), mapping unit names to prerequisite-name lists. All referenced units are keys. Repeatedly choose the alphabetically smallest currently ready unit. Return the complete order or [] if any cycle prevents completion. Do not mutate the dictionary or lists.',
        'def schedule_units(dependencies):\n    remaining={name:set(needs) for name,needs in dependencies.items()}\n    order=[]\n    while remaining:\n        ready=sorted(name for name,needs in remaining.items() if not needs)\n        if not ready: return []\n        chosen=ready[0]\n        order.append(chosen)\n        del remaining[chosen]\n        for needs in remaining.values(): needs.discard(chosen)\n    return order',
        [('schedule_units',[{'c':['a'],'b':[],'a':[]}],['a','b','c']),('schedule_units',[{'a':['b'],'b':['a']}],[]),('schedule_units',[{}],[]),('schedule_units',[{'z':[],'a':['z'],'b':[]}],['b','z','a'])])
    code('Test-driven fixing','integer_square_bound',
        'Implement floor_root(n) for nonnegative integer n, returning integer r with r*r <= n < (r+1)*(r+1). Include large integers; floating-point rounding must not change the answer.',
        'def floor_root(n):\n    low,high=0,n+1\n    while low+1<high:\n        middle=(low+high)//2\n        if middle*middle<=n: low=middle\n        else: high=middle\n    return low',
        [('floor_root',[0],0),('floor_root',[1],1),('floor_root',[80],8),('floor_root',[81],9),('floor_root',[1000000000000000000000001],1000000000000)])
    code('Test-driven fixing','dotted_release_order',
        'Implement compare_release(a,b). Inputs are nonempty dot-separated nonnegative decimal components. Compare numeric components, treating missing trailing components as zero. Return exactly -1, 0 or 1; leading zeros have no significance.',
        "def compare_release(a,b):\n    left=[int(x) for x in a.split('.')]\n    right=[int(x) for x in b.split('.')]\n    for i in range(max(len(left),len(right))):\n        x=left[i] if i<len(left) else 0\n        y=right[i] if i<len(right) else 0\n        if x!=y: return -1 if x<y else 1\n    return 0",
        [('compare_release',['2.09','2.9.0'],0),('compare_release',['1.10','1.2'],1),('compare_release',['4','4.0.1'],-1),('compare_release',['0.0','0'],0)])
    code('Test-driven fixing','wildcard_full_match',
        'Implement wildcard_fit(text,pattern). In pattern, ? matches exactly one character and * matches any sequence including empty. Other characters match literally. Match the ENTIRE text and return bool. Inputs contain lowercase ASCII letters, ? and * only in patterns.',
        "def wildcard_fit(text,pattern):\n    row=[True]+[False]*len(text)\n    for token in pattern:\n        new=[row[0] and token=='*']\n        for j,char in enumerate(text,1):\n            new.append((row[j] or new[j-1]) if token=='*' else row[j-1] and (token=='?' or token==char))\n        row=new\n    return row[-1]",
        [('wildcard_fit',['abc','a*c'],True),('wildcard_fit',['abc','a?'],False),('wildcard_fit',['','**'],True),('wildcard_fit',['','?'],False),('wildcard_fit',['abbbc','a*b?c'],True),('wildcard_fit',['cat','*dog*'],False)])
    code('Test-driven fixing','smallest_absent_positive',
        'Implement absent_positive(values): return the smallest positive integer not present in an integer list. Ignore zero/negative values; do not mutate the list.',
        'def absent_positive(values):\n    present=set(values)\n    candidate=1\n    while candidate in present: candidate+=1\n    return candidate',
        [('absent_positive',[[3,4,-1,1]],2),('absent_positive',[[]],1),('absent_positive',[[1,2,2,3]],4),('absent_positive',[[0,-4,8]],1)])

    tool_specs=[
      ('symbol_scope_query','Locate declarations matching ^render_ in Python files under ui/, excluding generated files, with at most 7 results.',
       {'symbol_query':{'pattern':'string','scope':{'roots':'array of strings','language':'string','exclude_generated':'boolean'},'limit':'integer'},'text_query':{'literal':'string','paths':'array of strings'}},
       {'tool':'symbol_query','arguments':{'pattern':'^render_','scope':{'roots':['ui/'],'language':'python','exclude_generated':True},'limit':7}}),
      ('read_disjoint_ranges','Read lines 3 through 8 AND 21 through 24, inclusive, from src/session.py at revision HEAD. Preserve that range order. Do not read the whole file.',
       {'read_ranges':{'path':'string','revision':'string','ranges':'array of {start: integer, end: integer}'},'read_whole':{'path':'string'}},
       {'tool':'read_ranges','arguments':{'path':'src/session.py','revision':'HEAD','ranges':[{'start':3,'end':8},{'start':21,'end':24}]}}),
      ('test_execution_environment','Run pytest on tests/test_cache.py::test_expiry, in cwd backend, with environment TZ=UTC and timeout 45 seconds, stopping after the first failure. Choose the test runner, not a shell.',
       {'pytest_run':{'nodeids':'array of strings','cwd':'string','env':'object of string values','timeout_seconds':'integer','max_failures':'integer'},'shell_run':{'command':'string'}},
       {'tool':'pytest_run','arguments':{'nodeids':['tests/test_cache.py::test_expiry'],'cwd':'backend','env':{'TZ':'UTC'},'timeout_seconds':45,'max_failures':1}}),
      ('repository_metadata_subset','Inspect the current branch and working-tree status of repository workspace. Request exactly fields branch and status in that order, include untracked files, and omit optional revision because no revision was requested.',
       {'repo_inspect':{'root':'string','fields':'array of strings','include_untracked':'boolean','revision':'optional string'},'repo_history':{'root':'string','count':'integer'}},
       {'tool':'repo_inspect','arguments':{'root':'workspace','fields':['branch','status'],'include_untracked':True}}),
      ('diagnostic_severity_filter','Fetch existing diagnostics for src/io.py and src/app.py in that order. Include only errors, group by file, and set cursor to JSON null for the first page. Do not run tests.',
       {'diagnostics_list':{'paths':'array of strings','filter':{'severities':'array of strings'},'group_by':'string','cursor':'string or null'},'pytest_run':{'nodeids':'array of strings'}},
       {'tool':'diagnostics_list','arguments':{'paths':['src/io.py','src/app.py'],'filter':{'severities':['error']},'group_by':'file','cursor':None}}),
      ('ordered_inspection_plan','Submit a read-only plan: first read the whole file pkg/routes.py; then run the test node tests/test_routes.py::test_lookup. Use step ids inspect and verify, in that order; verify depends on inspect. The first step has no dependencies.',
       {'submit_plan':{'steps':'array of {id: string, tool: string, arguments: object, depends_on: array of strings}'},'read_whole':{'path':'string'},'pytest_run':{'nodeids':'array of strings'}},
       {'tool':'submit_plan','arguments':{'steps':[{'id':'inspect','tool':'read_whole','arguments':{'path':'pkg/routes.py'},'depends_on':[]},{'id':'verify','tool':'pytest_run','arguments':{'nodeids':['tests/test_routes.py::test_lookup']},'depends_on':['inspect']}]}})
    ]
    for family,request,schemas,expected in tool_specs:
        ROWS.append({'id':'v1_'+family,'family':family,'category':'Tool-call formatting','response_mode':'tool_call_json',
          'prompt':request+'\nAvailable mock tools and argument schemas: '+json.dumps(schemas)+
          '\nReturn exactly one bare JSON object with tool (string) and arguments (object), no other keys, prose or Markdown fences. Use exactly the documented arguments for the selected tool, including nested keys; omit optional fields unless requested. Array order follows the request. No extra keys at any level. Key order and JSON whitespace do not matter. These are mock calls; do not execute anything.',
          'expected':expected,'reference':json.dumps(expected)})

    structured('Small repository reasoning','context_suppression_flow',{
      'gate_v1.py':"class QuietGate:\n    def __init__(self,events): self.events=events\n    def __enter__(self):\n        self.events.append('enter')\n        return self\n    def __exit__(self,kind,value,tb):\n        self.events.append('exit')\n        return kind is ValueError\n",
      'service_v1.py':"from gate_v1 import QuietGate\ndef guarded_events():\n    events=[]\n    with QuietGate(events):\n        events.append('work')\n        raise ValueError('stop')\n        events.append('unreachable')\n    events.append('after')\n    return events\n",
      'launch_v1.py':'import json\nfrom service_v1 import guarded_events\nprint(json.dumps(guarded_events()))\n'},
      ['enter','work','exit','after'],'context_manager_suppresses_value_error','the context manager suppresses ValueError so execution resumes after the with block')
    structured('Small repository reasoning','snapshot_unregister_dispatch',{
      'bus_v1.py':'handlers={}\ndef dispatch_snapshot():\n    return [fn() for fn in list(handlers.values())]\n',
      'plugin_v1.py':"import bus_v1\ndef first_plugin():\n    bus_v1.handlers.pop('second',None)\n    return 'first'\ndef second_plugin(): return 'second'\nbus_v1.handlers['first']=first_plugin\nbus_v1.handlers['second']=second_plugin\n",
      'launch_v1.py':'import json\nimport bus_v1\nimport plugin_v1\nprint(json.dumps([bus_v1.dispatch_snapshot(),bus_v1.dispatch_snapshot()]))\n'},
      [['first','second'],['first']],'dispatch_uses_snapshot_before_removal','removal changes future dispatch but not the callback snapshot already being iterated')
    structured('Small repository reasoning','layered_configuration_deletion',{
      'settings_v1.py':"from collections import ChainMap\ndef layered_settings():\n    defaults={'region':'west','workers':3}\n    local={'workers':5}\n    effective=ChainMap(local,defaults)\n    del effective['workers']\n    effective['region']='east'\n    return [dict(effective),local,defaults]\n",
      'launch_v1.py':'import json\nfrom settings_v1 import layered_settings\nprint(json.dumps(layered_settings()))\n'},
      [{'region':'east','workers':3},{'region':'east'},{'region':'west','workers':3}],
      'chainmap_writes_first_layer_reads_fallback','deletion exposes a default while assignment changes only the first map')
    structured('Small repository reasoning','captured_default_export',{
      'pricing_v1.py':'def price_units(n): return n*3\n',
      'facade_v1.py':'from pricing_v1 import price_units as quote_units\n',
      'client_v1.py':'import pricing_v1\nfrom facade_v1 import quote_units\ndef invoice_units(n,quote=quote_units):\n    return [quote(n),pricing_v1.price_units(n)]\n',
      'launch_v1.py':'import json\nimport pricing_v1\nfrom client_v1 import invoice_units\npricing_v1.price_units=lambda n:n*7\nprint(json.dumps(invoice_units(4)))\n'},
      [12,28],'default_retains_original_function_module_lookup_changes','the default captured the re-exported function before the module attribute was replaced')
    structured('Small repository reasoning','cached_property_refresh',{
      'measure_v1.py':'from functools import cached_property\nclass Reading:\n    def __init__(self):\n        self.raw=3\n        self.calls=0\n    @cached_property\n    def scaled(self):\n        self.calls+=1\n        return self.raw*4\n',
      'refresh_v1.py':'def refresh_reading(reading):\n    before=reading.scaled\n    reading.raw=8\n    stale=reading.scaled\n    del reading.scaled\n    return [before,stale,reading.scaled,reading.calls]\n',
      'launch_v1.py':'import json\nfrom measure_v1 import Reading as Sample\nfrom refresh_v1 import refresh_reading\nprint(json.dumps(refresh_reading(Sample())))\n'},
      [12,12,32,2],'cached_property_recomputes_only_after_deletion','changing the source does not invalidate a cached property; deleting the cached attribute does')
    structured('Small repository reasoning','shared_memoized_dependency',{
      'cache_v1.py':'memo={}\nvisits=[]\ndef measured_square(n):\n    if n not in memo:\n        visits.append(n)\n        memo[n]=n*n\n    return memo[n]\n',
      'left_v1.py':'from cache_v1 import measured_square\ndef left_value(): return measured_square(6)+1\n',
      'right_v1.py':'from cache_v1 import measured_square as sq\ndef right_value(): return sq(6)+sq(2)\n',
      'launch_v1.py':'import json\nimport cache_v1\nfrom left_v1 import left_value\nfrom right_v1 import right_value\nprint(json.dumps([left_value(),right_value(),cache_v1.visits]))\n'},
      [37,40,[6,2]],'both_imports_share_one_memo_module','both dependency branches share the cache, so six is computed only once')

if __name__=='__main__':
    if (HERE/'frozen_manifest.json').exists():
        raise SystemExit('Frozen benchmark: rebuilding is forbidden.')
    author()
    assert len(ROWS)==48
    (HERE/'tasks.json').write_text(json.dumps(ROWS,indent=2,ensure_ascii=False)+'\n')
    print('Authored 48 tasks; no model called.')
