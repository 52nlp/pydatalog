"""
pyDatalog

Copyright (C) 2012 Pierre Carbonnelle
Copyright (C) 2004 Shai Berger

This library is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation; either version 2 of the
License, or (at your option) any later version.

This library is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc.  51 Franklin St, Fifth Floor, Boston, MA 02110-1301
USA

This work is derived from Pythologic, (C) 2004 Shai Berger, 
in accordance with the Python Software Foundation licence.
(See http://code.activestate.com/recipes/303057/ and
http://www.python.org/download/releases/2.0.1/license/ )

"""

"""
TODO:
* expression in == operator see __iadd__ and __radd__
* test factorial
* package for release on pyPi

Roadmap / nice to have:
* Windows binaries
* avoid stack overflow with deep recursion
* debugging tools
* save / load database in file
* negation
* comparison (<, >, ...)
* parse(prolog_syntax) using pyparsing
* multicore using lua lanes

Limitations:
    No negations
    No expressions in =
    head is only one predicate

Interface of datalog engine in lua :
    make_var(id) --> { id: ) unique, inherits from Var
    make_const(id) --> { id: } unique, inherits from Const
    make_pred(name, arity) -->  { id: , db: { <clause ID>: }} unique, where id = name/arity.  (Called by make_pred)
    get_name(pred) = 
    get_arity(pred) = 
    make_literal(pred_name, terms) --> { pred: , id: , <i>: , tag: } 
            where id represents name, terms; 
            where tag is used as a key to literal by the subgoal table
    make_clause(head, body) = { head: , <i>: }
    insert(pred) = (called by insert)
    remove(pred) = 
    assert(clause) --> clause or nil
    retract(clause) --> clause
    save() = 
    restore() = 
    copy(src=None) = 
    revert(clone) = 
    ask(literal) = {name: , arity: , <i>: {i: }} or nil
    add_iter_prim(name, arity, iter) = 

    environment : mapping from variables to terms

Vocabulary:
    q(X):- q(a)
        a is a variable
        X is a constant
        q is a predicate
        q(a) is a literal
        q(a):-c is a clause

"""
import lupa
import os
import string
from lupa import LuaRuntime

class Symbol:
    """
    can be constant, variable or predicate name
    ask() creates a query
    created when analysing the datalog program
    """
    def __init__ (self, name, datalog_engine):
        self.name = name
        self.datalog_engine = datalog_engine # needed to create Literal
        self.type = 'variable' if (name[0] in string.uppercase) else 'constant'
        if self.type == 'variable':
            self.lua = datalog_engine._make_var(name)
        else:
            self.lua = datalog_engine._make_const(name)
        
    def __call__ (self, *args):
        "time to create a literal !"
        if self.name == 'ask':
            # TODO check that there is only one argument
            return self.datalog_engine._ask_literal(args[0])
        elif self.type == 'variable':
            raise TypeError("predicate name must start with a lower case : %s" % self.name)
        else:
            return Literal(self.datalog_engine, self.name, args)

    def __eq__(self, other):
        return Literal(self.datalog_engine, "=", (self, other))
    
    def __str__(self):
        return self.name

class Literal:
    """
    created by source code like 'p(a, b)'
    unary operator '+' means insert it as fact
    binary operator '+' means 'and', and returns a Body
    operator '<=' means 'is true if', and creates a Clause
    """
    def __init__(self, datalog_engine, predicate_name, terms):
        # TODO verify that terms are not Literals
        self.datalog_engine = datalog_engine # needed to insert facts, clauses
        self.predicate_name = predicate_name
        self.terms = terms
        tbl = datalog_engine.lua.eval('{ }')
        for a in terms:
            if isinstance(a, Symbol):
                datalog_engine._insert(tbl, a.lua)
            elif isinstance(a, str):
                datalog_engine._insert(tbl, datalog_engine._make_const(a))
            elif isinstance(a, Literal):
                raise SyntaxError("Literals cannot have a literal as argument : %s%s" % (predicate_name, terms))
            else:
                datalog_engine._insert(tbl, datalog_engine._make_const(str(a)))
        self.lua = datalog_engine._make_literal(predicate_name, tbl)
        #print pr(self.lua)

    def __pos__(self):
        " unary + means insert into datalog_engine as fact "
        # TODO verify that terms are constants !
        self.datalog_engine.assert_fact(self)

    def __neg__(self):
        " unary + means insert into datalog_engine as fact "
        # TODO verify that terms are constants !
        self.datalog_engine.retract_fact(self)

    def __le__(self, body):
        " head <= body"
        self.datalog_engine.add_clause(self, body)

    def __and__(self, literal):
        " literal & literal" 
        return Body(self, literal)

    def __str__(self):
        terms = list(map (str, self.terms))
        return str(self.predicate_name) + "(" + string.join(terms,',') + ")"

class Body:
    """
    created by p(a,b) + q(c,d)
    operator '+' means 'and', and returns a Body
    """
    def __init__(self, literal1, literal2):
        self.body = [literal1, literal2]

    def __and__(self, literal):
        self.body.append(literal) 
        return self

class Datalog_engine:
    """
    wrapper of datalog engine in lua
    """
    def __init__(self):
        self.clauses = []
        self.lua = LuaRuntime()
        lua_program_path = os.path.join(os.path.dirname(__file__), 'pyDatalog.lua')
        lua_program = open(lua_program_path).read()
        self.lua.execute(lua_program)
        self._insert = self.lua.eval('table.insert')
        self._make_const = self.lua.eval('datalog.make_const')
        self._make_var = self.lua.eval('datalog.make_var')
        self._make_literal = self.lua.eval('datalog.make_literal')
        self._make_clause = self.lua.eval('datalog.make_clause')
        self._assert = self.lua.eval('datalog.assert')
        self._retract = self.lua.eval('datalog.retract')
        self._ask = self.lua.eval('datalog.ask')
        self._db = self.lua.eval('datalog.db')

    def add_symbols(self, names, vars):
        for name in names:
            if not name.startswith('_'):
                vars[name] = Symbol(name, self)            
        
    def assert_fact(self, literal):
        tbl = self.lua.eval('{ }')
        clause = self._make_clause(literal.lua, tbl)
        self._assert(clause)
        #print pr(self._db)
        
    def retract_fact(self, literal):
        tbl = self.lua.eval('{ }')
        clause = self._make_clause(literal.lua, tbl)
        self._retract(clause)

    def add_clause(self,head,body):
        tbl = self.lua.eval('{ }')
        if isinstance(body, Body):
            for a in body.body:
                self._insert(tbl, a.lua)
            self.clauses.append((head, body.body))
        else: # body is a literal
            print(body)
            self._insert(tbl, body.lua)
            self.clauses.append((head,[body]))
        clause = self._make_clause(head.lua, tbl)
        self._assert(clause)
        #print pr(clause)
        
    class _NoCallFunction:
        """
        This class prevents a call to a datalog program
        """
        def __call__(self):
            raise TypeError("Datalog programs are not callable")
    
    def add_program(self, func):
        """
        A helper for decorator implementation
        """
        try:
            code = func.__code__
        except:
            raise TypeError("function or method argument expected")
        names = set(code.co_names)
        defined = set(code.co_varnames).union(set(func.__globals__.keys())) # local variables and global variables
        defined = defined.union(__builtins__)
        defined.add('None')
        newglobals = func.__globals__.copy()
        i = None
        for name in names.difference(defined): # for names that are not defined
            if not name.startswith('_'):
                self.add_symbols((name,), newglobals)
                # newglobals[name] = Symbol(name, self)
            else:
                newglobals[name] = i
        exec(code, newglobals)
        return self._NoCallFunction()
    
    def _ask_literal(self, literal): # called by Literal
        print("asking : %s" % str(literal))
        lua_result = self._ask(literal.lua)
        if not lua_result: return None
        # print pr(lua_result)
        result_set = set([lua_result[i+1] for i in range(len(lua_result))])
        result = set(tuple(dict(lua_result[i+1]).values()) for i in range(len(lua_result)))
        print(result)
        return result
    
    def ask(self, code):
        ast = compile(code, '<string>', 'eval')
        newglobals = {}
        self.add_symbols(ast.co_names, newglobals)
        lua_code = eval(code, newglobals)
        return self._ask_literal(lua_code)

    def execute(self, code):
        ast = compile(code, '<string>', 'exec')
        newglobals = {}
        self.add_symbols(ast.co_names, newglobals)
        exec ast in newglobals

    def prt(self):
        """
        TODO Print the clauses
        """
        for (h,b) in self.clauses:
            if isinstance(b, list):
                print(h, ":-", string.join(list(map(str, b)), " , "), ".")
            else:
                print(h, ":-", str(b), ".")

def program(datalog_engine):
    """
    A decorator for datalog program
    """
    return datalog_engine.add_program

def pr(a, level=0):
    try:
        #if isinstance(a, 'Lua_table'):
        if level<3:
            return [ (x[0], pr(x[1], level+1)) for x in list(a.items()) ]
        else:
            return [ (x[0], x[1]) for x in list(a.items()) ]

    except:
        return a
