#include "HintDefs.h"
#include "Parsers.h"
#include "ReplaceFunctionDefWithDecl.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <system_error>
#include <utility>

#include <tree_sitter/api.h>

static void printHintsVocabulary() {
  std::cout << '[';
  for (size_t I = 0; I < std::size(HintsVocabulary); ++I) {
    if (I > 0)
      std::cout << ',';
    // For simplicity, we assume no character needs escaping for JSON (always
    // true for replacement strings in clang_delta).
    std::cout << '"' << HintsVocabulary[I] << '"';
  }
  std::cout << "]\n";
}

static bool readFile(const std::string &Path, std::string &Contents) {
  std::error_code Error;
  auto Size = std::filesystem::file_size(Path, Error);
  if (Error) {
    std::cerr << "Failed to obtain size of file " << Path << " : "
              << Error.message() << "\n";
    return false;
  }
  Contents.resize(Size);
  std::ifstream File(Path, std::ios::binary);
  if (File.fail()) {
    std::cerr << "Failed to read file " << Path << "\n";
    return false;
  }
  File.read(Contents.data(), Size);
  auto ActuallyRead = File.gcount();
  Contents.resize(ActuallyRead);
  return true;
}

int main(int argc, char *argv[]) {
  std::ios::sync_with_stdio(false); // speed up C++ I/O streams

  if (argc != 2) {
    std::cerr << "Usage: " << argv[0] << " input/file/path\n";
    return -1;
  }
  const std::string InputPath = argv[1];

  // Prepare the common parsing state.
  std::unique_ptr<TSParser, decltype(&ts_parser_delete)> Parser(
      ts_parser_new(), ts_parser_delete);
  ts_parser_set_language(Parser.get(), tree_sitter_cpp());
  FuncDefWithDeclReplacer funcDefWithDeclReplacer;

  // Parse the input.
  std::string Contents;
  if (!readFile(InputPath, Contents)) {
    // The error details are logged by the function.
    return 1;
  }
  std::unique_ptr<TSTree, decltype(&ts_tree_delete)> Tree(
      ts_parser_parse_string(Parser.get(), /*old_tree=*/nullptr,
                             Contents.c_str(), Contents.length()),
      ts_tree_delete);
  if (!Tree) {
    std::cerr << "Failed to parse " << InputPath << "\n";
    return 1;
  }

  // Run heuristics and emit hints.
  printHintsVocabulary();
  funcDefWithDeclReplacer.processParsedFile(*Tree);
}
