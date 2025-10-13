/* topformflat.l; see License.txt for copyright and terms of use
 *
 * Scott McPeak        <smcpeak@cs.berkeley.edu>
 *
 * flatten all toplevel forms to single lines.
 * very heuristic... */

%{
#include <assert.h>
#include <limits.h>
#include <stdlib.h>     // atoi

// debugging diagnostic, emitted when enabled
void diag(char const *str);

// handle possible toplevel block boundaries if nesting <= threshold
void possibleChunkBegin(int pos);
void possibleChunkEnd(int pos);

// index of file that's currently being parsed, or -1 for a single-file input.
int path_id = 0;

// index of byte where the current yytext ends in the input.
int token_end_pos = 0;

// index of byte where the current toplevel block started.
int chunk_start_pos = 0;

// keep track of brace nesting (0 means not inside any pair)
int nesting = 0;

// nesting threshold; when nesting is greater than threshold,
// newlines are suppressed
int threshold = 0;

// indices of bytes of the most recent consecutive whitespace block.
int whitespace_start_pos = -1;
int whitespace_end_pos = -1;

// update the position whenever a token is about to be processed
// (this macro is triggered by Flex prior to executing the matched rule’s action).
#define YY_USER_ACTION token_end_pos += yyleng;

%}

/* optimize the scanner for performance */
%option fast
/* dsw: don't define yyunput() */
%option nounput
/* support all characters, including UTF-8 */
%option 8bit

/* start condition for strings */
%x STRING
%x CHARLIT


%%

";"           { possibleChunkEnd(token_end_pos); }

"/\n"         { }     /* end of C comment */

"{"           { nesting++;
                possibleChunkBegin(token_end_pos);      // so the header is separated from the components
              }

"}"(";"?)     { nesting--;
                possibleChunkEnd(token_end_pos);
              }

  /* parse a preprocessor directive:
   * start of the line with possible leading whitespaces, a hash, then some non-newlines.
   * then, possibly, an escaped newline followed by more non-newlines (repeat as needed).
   * finally, a newline */
^[[:blank:]]*"#".*("\\\n".*)*"\n" {
                int start_pos = token_end_pos - yyleng;
                if (start_pos > 0)
                  possibleChunkEnd(start_pos - 1);          /* make sure starts on own line */
                possibleChunkEnd(token_end_pos - 1);        /* minus one to preserve the newline */
                possibleChunkBegin(token_end_pos);          /* don't eat the newline in the subsequent chunk */
              }

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

"\n"          |                                             /* line break, not matched in any other rule */
[[:blank:]]+  {                                             /* chunk of whitespaces */
                int token_start_pos = token_end_pos - yyleng;
                // Start a new whitespace block, unless the previous one is to be continued.
                if (token_start_pos != whitespace_end_pos)
                  whitespace_start_pos = token_start_pos;
                whitespace_end_pos = token_end_pos;
              }

.             { }

%%

void diag(char const *str)
{
  //printf("%s", str);
}

void possibleChunkBegin(int pos)
{
  if (nesting <= threshold) {
    chunk_start_pos = pos;
  }
}

void chunkEnd(int pos)
{
  if (chunk_start_pos >= pos)
    return;  // Empty chunk.
  if (whitespace_start_pos <= chunk_start_pos && pos <= whitespace_end_pos)
    return;  // Skip deleting chunks consisting of whitespaces only.
  printf("{\"p\":[{\"l\":%d,\"r\":%d", chunk_start_pos, pos);
  if (path_id != -1)
    printf(",\"p\":%d", path_id);
  printf("}]}\n");
}

void possibleChunkEnd(int pos)
{
  assert(path_id != INT_MAX);
  // Only attempt deleting chunks exactly at the specified nesting.
  if (nesting == threshold)
    chunkEnd(pos);
  possibleChunkBegin(pos);
}

void reset_to_initial_state(void) {
  BEGIN(INITIAL);
  token_end_pos = 0;
  chunk_start_pos = 0;
  nesting = 0;
  whitespace_start_pos = -1;
  whitespace_end_pos = -1;
}

int yywrap(void) {
  // In case there's some chunk of text remaining - e.g., if the file is not
  // EOL-terminated and the last line was a preprocessor directive.
  if (nesting >= threshold)
    chunkEnd(token_end_pos);

  if (path_id == -1) {
    path_id = INT_MAX;
    return 1;
  }
  char *path = NULL;
  size_t size = 0;
  ssize_t nread = getdelim(&path, &size, 0, stdin);
  if (nread == -1 || !strlen(path)) {
    free(path);
    path_id = INT_MAX;
    return 1;
  }
  FILE* f = fopen(path, "r");
  if (!f) {
    fprintf(stderr, "Cannot open file: %s\n", path);
    free(path);
    path_id = INT_MAX;
    return 1;
  }
  free(path);
  if (yyin) {
    fclose(yyin);
    ++path_id;
  }
  yyin = f;
  reset_to_initial_state();
  yyrestart(yyin);
  return 0;
}

char *version = "2025.6.25";
int main(int argc, char *argv[])
{
  if (argc != 3) {
    printf("topformflat_hints version %s\n", version);
    printf("USAGE: %s threshold file >hints.jsonl\n", argv[0]);
    printf("  \"--\" can be specified instead of file, in which case input\n"
           "  file paths should be sent as null-character-separated list into\n"
           "  stdin.\n");
    printf("  The threshold (default: 0) specifies at what nesting level\n"
           "  of braces will line breaks be allowed (or inserted).  By\n"
           "  starting with 0, you get all top-level forms, one per line\n"
           "  (roughly).  Increasing the threshold leads to finer-grained\n"
           "  structure on each line.  The intent is to use the delta\n"
           "  minimizer on each level of granularity.\n");
    return 1;
  }

  threshold = atoi(argv[1]);    // user-specified threshold

  if (strcmp(argv[2], "--") == 0) {
    path_id = 0;
    yyin = NULL;
    if (yywrap())
      return 2;
  } else {
    path_id = -1;
    yyin = fopen(argv[2], "r");
    if (!yyin) {
      fprintf(stderr, "Cannot open file: %s\n", argv[2]);
      return 2;
    }
  }

  yylex();
  return 0;
}
