/*
 * Copyright (c) 2013, 2014, 2015, 2016 The University of Utah
 * All rights reserved.
 *
 * This file is distributed under the University of Illinois Open Source
 * License.  See the file COPYING for details.
 */

#ifndef DEFS_H
#define DEFS_H

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

/*
 * Stuff defined for us by the lex/flex-generated code.
 */
extern FILE *yyin;
extern int yylex(void);
extern char *yytext;
extern int yyleng;

/*
 * Stuff that we define within the lex/flex-generated code.
 */
extern int count;
extern int tok_end_pos;
void restart_with_new_file(void);

enum tok_kind {
  TOK_KEYWORD = 999,
  TOK_OP,
  TOK_IDENT,
  TOK_OTHER,
  TOK_NUMBER,
  TOK_WS,
  TOK_NEWLINE,
  TOK_STRING,
  TOK_UNKNOWN,
};

void process_token(enum tok_kind);

#define OK 51
#define STOP 71

#endif
