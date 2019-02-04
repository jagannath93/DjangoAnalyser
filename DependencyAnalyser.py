#!/usr/bin/env python

# Python Imports
import os
import sys
import ast
import uuid
import json
import argparse
from subprocess import PIPE
from subprocess import Popen
from collections import OrderedDict
#from prettytable import PrettyTable
#import importlib
#import symtable
#import inspect

# Django Imports
from django.db import models


# Setup django environment
home_dir = os.path.expanduser('~')
project_root = os.path.join(home_dir, 'django')
if project_root not in sys.path:
    sys.path.append(project_root)

settings_path = os.path.join(project_root, 'settings')
sys.path.append(settings_path)
#TODO: Add 'local' and 'dev' settings under respective conditions
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from django.conf import settings


# Globals
module_imports_map = OrderedDict()
target_mod_imports = []

# Classes
class NodeVisitor(ast.NodeVisitor):
    """
    Custom node visitor class.
    """
    def __init__(self, member):
        # member can be a Function or a Class
        self.member_name = member

    def visit(self, node, *args, **kwargs):
        #if hasattr(self, member_name):
        #    self.member_name = node.name
        result = super(NodeVisitor, self).visit(node, *args, **kwargs)
        if not result:
            result = []
        return result

    def generic_visit(self, node, *args, **kwargs):
        result = super(NodeVisitor, self).generic_visit(node, *args, **kwargs)
        if not result:
            result = []
        return result


    def visit_Import(self, node):
        internal_imports = {}
        for _import in node.names:
            _name = _import.name
            _import_statement = 'import '+_name
            if _import.asname:
                _name = _import.asname
                _import_statement += ' as '+_name
            internal_imports[_name] = [
                    #importlib.import_module(_name),
                    _import_statement,
                    #node.lineno,
                    #node.col_offset,
            ]
        module_imports_map[self.member_name]['source_mod_imports'].update(internal_imports)
        return []


    def visit_ImportFrom(self, node):
        internal_imports = {}
        _module_name = node.module
        for _import in node.names:
            _import_statement = 'from '+_module_name
            _name = _import.name
            _import_statement += ' import '+_name
            if _import.asname:
                _name = _import.asname
                _import_statement += ' as '+_name
            internal_imports[_name] = [
                    #importlib.import_module(_module_name),
                    _import_statement,
                    #node.lineno,
                    #node.col_offset,
            ]
        module_imports_map[self.member_name]['source_mod_imports'].update(internal_imports)
        return []

    def visit_ClassDef(self, node):
        result = {}
        _bases = []
        _decorators = []
        _children = []
        # bases
        for base_class in node.bases:
            _bases.extend(self.visit(base_class))
        # decorator_list
        for decorator in node.decorator_list:
            _decorators.extend(self.visit(decorator))
        # body
        for child_node in node.body:
            _children.extend(self.visit(child_node))

        _bases = list(set(_bases))
        _decorators = list(set(_decorators))
        _children = list(set(_children))

        if self.member_name == node.name:
            result = {
                'bases': _bases,
                'decorators': _decorators,
                'definition': _children,
            }
        else:
            result = _bases + _decorators + _children

        return result


    def visit_FunctionDef(self, node):
        result = {}
        _args = []
        _decorators = []
        _children = []
        # args
        args = node.args.args
        for arg in args:
            _args.extend(self.visit(arg))
        # decorator_list
        for decorator in node.decorator_list:
            _decorators.extend(self.visit(decorator))
        # body
        for child_node in node.body:
            _children.extend(self.visit(child_node))

        _args = list(set(_args))
        _decorators = list(set(_decorators))
        _children = list(set(_children))

        if self.member_name == node.name:
            result = {
                'arguments': _args,
                'decorators': _decorators,
                'definition': _children,
            }
        else:
            result = _args + _decorators + _children

        return result


    def visit_Call(self, node):
        result = []
        # args
        for arg in node.args:
            result.extend(self.visit(arg))
        # keywords
        for keyword in node.keywords:
            # Note: No need to take keyword.arg
            result.extend(self.visit(keyword.value))
        # kwargs
        if node.kwargs:
            result.extend(self.visit(node.kwargs))
        # starargs
        if node.starargs:
            result.extend(self.visit(node.starargs))
        # func
        result.extend(self.visit(node.func))
        return result


    def visit_Expr(self, node):
        result = []
        value = node.value
        result.extend(self.visit(value))
        return result


    def visit_UnaryOp(self, node):
        result = []
        operand = node.operand
        result.extend(self.visit(operand))
        return result


    def visit_BinOp(self, node):
        result = []
        # left
        left = node.left
        result.extend(self.visit(left))
        # right
        right = node.right
        result.extend(self.visit(right))
        return result


    def visit_If(self, node):
        result = []
        # test
        test = node.test
        result.extend(self.visit(test))
        # body
        body = node.body
        for child_node in body:
            result.extend(self.visit(child_node))
        # orelse
        orelse = node.orelse
        for child_node in orelse:
            result.extend(self.visit(child_node))
        return result


    def visit_While(self, node):
        result = []
        # test
        test = node.test
        result.extend(self.visit(test))
        # body
        body = node.body
        for child_node in body:
            result.extend(self.visit(child_node))
        # orelse
        orelse = node.orelse
        for child_node in orelse:
            result.extend(self.visit(child_node))
        return result


    def visit_Assign(self, node):
        # Assignment operation can have multiple targets
        # Type1 Ex: a = b = 2
        # Type2 Ex: a,b = func()
        result = []
        targets = node.targets
        for target in targets:
            result.extend(self.visit(target))
        # value attribute is not a list in assignment operation
        value = node.value
        result.extend(self.visit(value))
        return result


    def visit_AugAssign(self, node):
        result = []
        value = node.value
        result.extend(self.visit(value))
        return result


    def visit_Attribute(self, node):
        result = []
        value = node.value
        result.extend(self.visit(value))
        return result

    def visit_For(self, node):
        result = []
        # target
        target = node.target
        result.extend(self.visit(target))
        # iter
        iterator = node.iter
        result.extend(self.visit(iterator))
        # body
        body = node.body
        for child_node in body:
            result.extend(self.visit(child_node))
        # orelse
        orelse = node.orelse
        for child_node in orelse:
            result.extend(self.visit(orelse))
        return result


    def visit_Keyword(self, node):
        result = []
        # value
        value = node.value
        result.extend(self.visit(value))
        return result


    def visit_Dict(self, node):
        result = []
        # values
        values = node.values
        for value in values:
            result.extend(self.visit(value))
        return result


    def visit_BoolOp(self, node):
        result = []
        # values
        values = node.values
        for value in values:
            result.extend(self.visit(value))
        return result


    def visit_Compare(self, node):
        result = []
        # left
        left = node.left
        result.extend(self.visit(left))
        # comparators
        comparators = node.comparators
        for comparator in comparators:
            result.extend(self.visit(comparator))
        return result


    def visit_Return(self, node):
        result = []
        # value
        value = node.value
        result.extend(self.visit(value))
        #print result
        return result


    def visit_List(self, node):
        result = []
        # values
        values = node.elts
        for value in values:
            result.extend(self.visit(value))
        return result


    def visit_Tuple(self, node):
        result = []
        values = node.elts
        for value in values:
            result.extend(self.visit(value))
        return result


    def visit_Set(self, node):
        result = []
        values = node.elts
        for value in values:
            result.extend(self.visit(value))
        return result


    def visit_Lambda(self, node):
        result = []
        body = node.body
        for child_node in body:
            result.extend(self.visit(child_node))
        return result


    def visit_Subscript(self, node):
        result = []
        value = node.value
        result.extend(self.visit(value))
        return result


    def visit_Assert(self, node):
        result = []
        # left
        left = node.left
        result.extend(self.visit(left))
        # comparators
        comparators = node.comparators
        for comparator in comparators:
            result.extend(self.visit(comparator))
        return result


    def visit_Raise(self, node):
        result = []
        _type = node.type
        result.extend(self.visit(_type))
        return result


    def visit_Name(self, node):
        #if node.id in ['True', 'False', 'None']:
        #    return []
        #else:
        return [node.id]

# Methods
def process_git_grep_command(cmd, tag):
    _files = []
    templates_path = settings.TEMPLATES_PATH
    os.chdir(templates_path)
    #TODO: Add template directory path for searching
    _stdout = Popen(cmd, stdout=PIPE, shell=True)
    (output, error) = _stdout.communicate()
    if output:
        outputs = output.split('\n')
        for output in outputs:
            if output:
                tmp = output.split(':')[1]
                tmp = tmp.replace(" ", "") \
                        .replace("{%", "").replace("%}", "") \
                        .replace(tag, "", 1) \
                        .replace("\"", "").replace("'", "")

                _file = os.path.join(templates_path, tmp)
                if os.path.exists(_file):
                    _files.append(_file)
    return _files


########################
def search_member(member, src_path=''):
    def get_absolute_file_path(cmd):
        _stdout = Popen(cmd, stdout=PIPE, shell=True)
        (output, error) = _stdout.communicate()
        if output:
            output = output.split('\n')[0]
            relative_path = output.split(':')[0]
            absolute_path = os.path.join(project_root, relative_path)
            return absolute_path

    # check if a function exists with this name
    _type = 'def'
    cmd = 'git grep "' + _type + ' ' + member + '("'
    if src_path:
        cmd += ' '+src_path
    result = get_absolute_file_path(cmd)
    if result:
        return result

    # check if a class exists with this name
    _type = 'class'
    cmd = 'git grep "' + _type +' '+ member +'("'
    result =  get_absolute_file_path(cmd)
    if result:
        return result
    return ''


def read_file(abs_path):
    _str = ''
    with open(abs_path, 'r') as f:
        _str = f.read()
    return _str


def get_ast_module_tree(abs_path):
    module_as_string = read_file(abs_path)
    tree = ast.parse(module_as_string)
    return tree


def get_module_imports(module_tree):
    module_imports = {}
    for node in module_tree.body:
        # Handles Import statements
        if isinstance(node, ast.Import):
            for _import in node.names:
                _name = _import.name
                _import_statement = 'import '+_name
                if _import.asname:
                    _name = _import.asname
                    _import_statement += ' as '+_name
                module_imports[_name] = [
                        #importlib.import_module(_name),
                        _import_statement,
                        #node.lineno,
                        #node.col_offset,
                ]

        # Handles From..Import statements
        if isinstance(node, ast.ImportFrom):
            _module_name = node.module
            for _import in node.names:
                _import_statement = 'from '+_module_name
                _name = _import.name
                _import_statement += ' import '+_name
                if _import.asname:
                    _name = _import.asname
                    _import_statement += ' as '+_name
                module_imports[_name] = [
                        #importlib.import_module(_module_name),
                        _import_statement,
                        #node.lineno,
                        #node.col_offset,
                ]

    return module_imports


def analyse_member(member, src_path='', target_path=''):
    dependencies = {}
    _map = {}

    if not member:
        return

    result = {}
    abs_path = search_member(member, src_path)
    if abs_path:
        src_tree = get_ast_module_tree(abs_path)
        source_mod_imports = get_module_imports(src_tree)
        module_imports_map[member] = {
            'source_mod_imports': source_mod_imports,
        }

        # get dependency imports of the given member
        for node in src_tree.body:
            # Handles Class and Function Definitions
            if isinstance(node, ast.ClassDef) or \
                    isinstance(node, ast.FunctionDef):
                if node.name == member:
                    he_visitor = NodeVisitor(member)
                    dependencies.update(he_visitor.visit(node))
                    break

        _imports = set(source_module_imports.keys())
        #_builtins = set(module.__builtins__)
        #_builtins = set([])
        _map['import_dependencies'] = OrderedDict()
        #_map['builtin_dependencies'] = OrderedDict()
        _src_imports_list = []
        src_mod_imports = module_imports_map[member]['source_mod_imports']
        for key, value in dependencies.items():
            import_dependencies = _imports.intersection(set(value))
            #builtin_dependencies = _builtins.intersection(set(value))
            _list = [src_mod_imports[_import][0] for _import in import_dependencies]
            _src_imports_list.extend(_list)
            #_map['import_dependencies'][key] = map( \
            #    lambda v: {v : global_imports[v]}, import_dependencies)
            #_map['builtin_dependencies'][key] = map( \
            #    lambda v: v, builtin_dependencies)

        result = {
            'source_dependency_imports': _src_imports_list,
        }

        # required imports at target
        if target_path:
            _target_imports = [_import[0] for _import in target_mod_imports.values()]
            target_imports_set = set(_target_imports)
            src_dependencies_set = set(_src_imports_list)
            req_imports_set = \
            src_dependencies_set - (target_imports_set.intersection(src_dependencies_set))

            result.update({
                'required_target_imports': list(req_imports_set),
            })
    return result


def show_member_imports(members, src_path='', target_path=''):
    # reset global variables
    module_imports_map.clear()
    target_mod_imports[:] = []

    if target_path:
        abs_path = os.path.join(project_root, target_path)
        target_tree = get_ast_module_tree(abs_path)
        _target_imports = get_module_imports(target_tree)
        target_mod_imports.extend(_target_imports)

    for member in members:
        print "\nMember: " + member
        result = analyse_member(member, src_path, target_path)
        if result:
            src_dependency_imports = result['source_dependency_imports']
            src_mod_imports_no = len(module_imports_map[member]['source_mod_imports'].keys())
            dependency_imports_no = len(src_dependency_imports)
            print "Total source module imports (global + local): " + str(src_mod_imports_no)
            print "Total dependency imports (global + local): " + str(dependency_imports_no)
            print "\nDEPENDENCY IMPORTS"
            for _import in src_dependency_imports:
                print _import

            if result.has_key('required_target_imports'):
                req_target_imports = result['required_target_imports']
                required_target_imports = len(req_target_imports)
                print "\nAdditional imports required in the target file: " + \
                    str(required_target_imports)
                print "REQUIRED IMPORTS"
                for _import in req_target_imports:
                    print _import

    print "\n"

# main
if __name__ == '__main__':
    member = ''
    src_path = ''
    target_path = ''

    os.chdir(project_root)

    parser = argparse.ArgumentParser()

    parser.add_argument('--members', '-m',
            nargs = '*',
            default = [],
            help = 'member names')

    parser.add_argument('--source', '-s',
            default = '',
            help = 'source file path(relative)')

    parser.add_argument('--target', '-t',
            default = '',
            help = 'target file path(relative)')

    parser.add_argument('--variables', '-v',
            nargs = '*',
            default = [],
            help = 'variable names')

    args = parser.parse_args()

    show_member_imports(
            args.members,
            args.source,
            args.target)

    get_assignment_value(
            args.members,
            args.variables)

