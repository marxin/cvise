%{
/*
 * Copyright (c) 2013 The University of Utah
 * All rights reserved.
 *
 * This file is distributed under the University of Illinois Open Source
 * License.  See the file COPYING for details.
 */
%}

D			[0-9]
L			[a-zA-Z_]
H			[a-fA-F0-9]
E			[Ee][+-]?{D}+
FS			(f|F|l|L)
IS			(u|U|l|L)*

%option noyywrap

%{

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include <defs.h>
#include <limits.h>

// update the position whenever a token is about to be processed
// (this macro is triggered by Flex prior to executing the matched rule’s action).
#define YY_USER_ACTION tok_end_pos += yyleng;

%}

%%

"auto"			{ process_token(TOK_KEYWORD); }
"break"			{ process_token(TOK_KEYWORD); }
"case"			{ process_token(TOK_KEYWORD); }
"char"			{ process_token(TOK_KEYWORD); }
"const"			{ process_token(TOK_KEYWORD); }
"continue"		{ process_token(TOK_KEYWORD); }
"default"		{ process_token(TOK_KEYWORD); }
"do"			{ process_token(TOK_KEYWORD); }
"double"		{ process_token(TOK_KEYWORD); }
"else"			{ process_token(TOK_KEYWORD); }
"enum"			{ process_token(TOK_KEYWORD); }
"extern"		{ process_token(TOK_KEYWORD); }
"float"			{ process_token(TOK_KEYWORD); }
"for"			{ process_token(TOK_KEYWORD); }
"goto"			{ process_token(TOK_KEYWORD); }
"if"			{ process_token(TOK_KEYWORD); }
"int"			{ process_token(TOK_KEYWORD); }
"long"			{ process_token(TOK_KEYWORD); }
"register"		{ process_token(TOK_KEYWORD); }
"return"		{ process_token(TOK_KEYWORD); }
"short"			{ process_token(TOK_KEYWORD); }
"signed"		{ process_token(TOK_KEYWORD); }
"sizeof"		{ process_token(TOK_KEYWORD); }
"static"		{ process_token(TOK_KEYWORD); }
"struct"		{ process_token(TOK_KEYWORD); }
"switch"		{ process_token(TOK_KEYWORD); }
"typedef"		{ process_token(TOK_KEYWORD); }
"union"			{ process_token(TOK_KEYWORD); }
"unsigned"		{ process_token(TOK_KEYWORD); }
"void"			{ process_token(TOK_KEYWORD); }
"volatile"		{ process_token(TOK_KEYWORD); }
"while"			{ process_token(TOK_KEYWORD); }

{L}({L}|{D})*		{ process_token(TOK_IDENT); }

0[xX]{H}+{IS}?		{ process_token(TOK_NUMBER); }
0{D}+{IS}?		{ process_token(TOK_NUMBER); }
{D}+{IS}?		{ process_token(TOK_NUMBER); }
L?'(\\.|[^\\'])+'	{ process_token(TOK_OTHER); }

{D}+{E}{FS}?		{ process_token(TOK_NUMBER); }
{D}*"."{D}+({E})?{FS}?	{ process_token(TOK_NUMBER); }
{D}+"."{D}*({E})?{FS}?	{ process_token(TOK_NUMBER); }

L?\"(\\.|[^\\"])*\"	{ process_token(TOK_STRING); }

"..."			{ process_token(TOK_OTHER); }
">>="			{ process_token(TOK_OP); }
"<<="			{ process_token(TOK_OP); }
"+="			{ process_token(TOK_OP); }
"-="			{ process_token(TOK_OP); }
"*="			{ process_token(TOK_OP); }
"/="			{ process_token(TOK_OP); }
"%="			{ process_token(TOK_OP); }
"&="			{ process_token(TOK_OP); }
"^="			{ process_token(TOK_OP); }
"|="			{ process_token(TOK_OP); }
">>"			{ process_token(TOK_OP); }
"<<"			{ process_token(TOK_OP); }
"++"			{ process_token(TOK_OP); }
"--"			{ process_token(TOK_OP); }
"->"			{ process_token(TOK_OP); }
"&&"			{ process_token(TOK_OP); }
"||"			{ process_token(TOK_OP); }
"<="			{ process_token(TOK_OP); }
">="			{ process_token(TOK_OP); }
"=="			{ process_token(TOK_OP); }
"!="			{ process_token(TOK_OP); }
";"			{ process_token(TOK_OP); }
("{"|"<%")		{ process_token(TOK_OP); }
("}"|"%>")		{ process_token(TOK_OP); }
","			{ process_token(TOK_OP); }
":"			{ process_token(TOK_OP); }
"="			{ process_token(TOK_OP); }
"("			{ process_token(TOK_OP); }
")"			{ process_token(TOK_OP); }
("["|"<:")		{ process_token(TOK_OP); }
("]"|":>")		{ process_token(TOK_OP); }
"."			{ process_token(TOK_OP); }
"&"			{ process_token(TOK_OP); }
"!"			{ process_token(TOK_OP); }
"~"			{ process_token(TOK_OP); }
"-"			{ process_token(TOK_OP); }
"+"			{ process_token(TOK_OP); }
"*"			{ process_token(TOK_OP); }
"/"			{ process_token(TOK_OP); }
"%"			{ process_token(TOK_OP); }
"<"			{ process_token(TOK_OP); }
">"			{ process_token(TOK_OP); }
"^"			{ process_token(TOK_OP); }
"|"			{ process_token(TOK_OP); }
"?"			{ process_token(TOK_OP); }
"#"                     { process_token(TOK_OTHER); }
"\\"                    { process_token(TOK_OTHER); }

"/*"        {
                int start_path_id = path_id;
                int prev = 0;
                for (;;)  {
                    int c = input();
                    if (c == EOF || path_id == INT_MAX)
                        break;
                    if (path_id != start_path_id) {
                        /* don't cross file boundaries */
                        unput(c);
                        break;
                    }
                    ++tok_end_pos;
                    if (c == '/' && prev == '*')
                        break;  /* found the end */
                    prev = c;
                }
            }

[ \t\v\n\f]		{ process_token(TOK_WS); }

.			{ fprintf (stderr, "didn't expect to see '%s'\n", yytext);
                          assert (0); }

%%

int count = 0;
// index of byte where the current yytext ends in the input.
int tok_end_pos = 0;

void restart_with_new_file(void) {
    BEGIN(INITIAL);
    YY_NEW_FILE;
}
