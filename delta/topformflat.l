/* topformflat.l; see License.txt for copyright and terms of use
 *
 * Scott McPeak        <smcpeak@cs.berkeley.edu>
 *
 * flatten all toplevel forms to single lines.
 * very heuristic... */

%{
#include <stdlib.h>     // atoi

// debugging diagnostic, emitted when enabled
void diag(char const *str);

// handle a possible newline insertion if nesting <= threshold
void possibleChunkEnd(int pos);

// index of byte where the current yytext ends in the input.
int token_end_pos = 0;

// index of byte where the current toplevel block started.
int chunk_start_pos = 0;

// keep track of brace nesting (0 means not inside any pair)
int nesting = 0;

// nesting threshold; when nesting is greater than threshold,
// newlines are suppressed
int threshold = 0;

// update the position whenever a token is about to be processed.
#define YY_USER_ACTION token_end_pos += yyleng;

%}

/* don't try to call yywrap() */
%option noyywrap
/* dsw: don't define yyunput() */
%option nounput

/* start condition for strings */
%x STRING
%x CHARLIT


%%

";"           { possibleChunkEnd(token_end_pos); }

"/\n"         { }     /* end of C comment */

"{"           { nesting++;
                possibleChunkEnd(token_end_pos);      // so the header is separated from the components
              }

"}"(";"?)     { nesting--;
                possibleChunkEnd(token_end_pos);
              }

  /* a hash, then some non-newlines.  then, possibly, an escaped
   * newline followed by more non-newlines (repeat as needed).
   * finally, a newline */
"#".*("\\\n".*)*"\n" {
                int hash_pos = token_end_pos - yyleng;
                possibleChunkEnd(hash_pos);                 /* make sure starts on own line */
                possibleChunkEnd(token_end_pos);
              }

"\n"          { }                                           /* not any above case, skip it*/

"//".*"\n"    { }                                           /* C++ comment */

"\""          { diag("<STR>"); BEGIN(STRING); }             /* start quote */

<STRING>{
  "\\"(.|\n)  { }                                           /* escaped character */
  "\""        { diag("</STR>"); BEGIN(INITIAL); }           /* close quote */
  (.|\n)      { }                                           /* ordinary char */
}

"\'"          { diag("<CHAR>"); BEGIN(CHARLIT); }           /* start tick */

<CHARLIT>{
  "\\"(.|\n)  { }                                           /* escaped character */
  "\'"        { diag("</CHAR>"); BEGIN(INITIAL); }          /* close tick */
  (.|\n)      {  }                                          /* ordinary char */
}

.             { }

%%

void diag(char const *str)
{
  //printf("%s", str);
}

void possibleChunkEnd(int pos)
{
  if (nesting <= threshold && chunk_start_pos < pos) {
    printf("{\"p\":[{\"l\":%d,\"r\":%d}]}\n", chunk_start_pos, pos);
    chunk_start_pos = pos;
  }
}

char *version = "2025.6.25";
int main(int argc, char *argv[])
{
  if (isatty(0)) {
    printf("topformflat_hints version %s\n", version);
    printf("usage: %s [threshold] <input.c >hints.jsonl\n", argv[0]);
    printf("  The threshold (default: 0) specifies at what nesting level\n"
           "  of braces will line breaks be allowed (or inserted).  By\n"
           "  starting with 0, you get all top-level forms, one per line\n"
           "  (roughly).  Increasing the threshold leads to finer-grained\n"
           "  structure on each line.  The intent is to use the delta\n"
           "  minimizer on each level of granularity.\n");
    return 0;
  }

  if (argc >= 2) {
    threshold = atoi(argv[1]);    // user-specified threshold
  }

  yyin = stdin;
  yylex();
  possibleChunkEnd(token_end_pos);
  return 0;
}
