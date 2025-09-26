#include "Parsers.h"
#include "Transformation.h"
#include "TransformationFactory.h"

#include <filesystem>
#include <fstream>
#include <ios>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <system_error>
#include <utility>
#include <vector>

#include <tree_sitter/api.h>

static void printVocab(const std::vector<std::string> &Vocab) {
  std::cout << '[';
  for (size_t I = 0; I < Vocab.size(); ++I) {
    if (I > 0)
      std::cout << ',';
    // For simplicity, we assume no character needs escaping for JSON (always
    // true for replacement strings in treesitter_delta).
    std::cout << '"' << Vocab[I] << '"';
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

std::unique_ptr<TSTree, decltype(&ts_tree_delete)>
parseFile(const std::string &Contents, TSParser *Parser) {
  return std::unique_ptr<TSTree, decltype(&ts_tree_delete)>(
      ts_parser_parse_string(Parser, /*old_tree=*/nullptr, Contents.c_str(),
                             Contents.length()),
      ts_tree_delete);
}

int main(int argc, char *argv[]) {
  std::ios::sync_with_stdio(false); // speed up C++ I/O streams

  if (argc != 3) {
    std::cerr << "Usage: " << argv[0] << " transformation input/file/path\n"
              << "  or, for multi-file, send the paths as newline-separated "
                 "list in stdin: "
              << argv[0] << " transformation --\n"
              << "transformation: one of \"replace-function-def-with-decl\", "
                 "\"erase-namespace\", \"remove-function\".\n";
    return -1;
  }
  const std::string TransformationName = argv[1];
  const std::string InputPathArg = argv[2];

  // Build the input file list.
  bool MultiFile = InputPathArg == "--";
  std::vector<std::filesystem::path> InputPaths;
  if (MultiFile) {
    std::string Line;
    while (std::getline(std::cin, Line, '\0')) {
      if (Line.empty())
        continue;
      InputPaths.push_back(std::move(Line));
    }
  } else {
    InputPaths.push_back(InputPathArg);
  }

  auto Transform = createTransformation(TransformationName);
  if (!Transform) {
    std::cerr << "Unknown transformation: " << TransformationName << "\n";
    return -1;
  }
  std::vector<std::string> Vocab = Transform->getVocabulary();
  if (MultiFile)
    Vocab.insert(Vocab.end(), InputPaths.begin(), InputPaths.end());
  printVocab(Vocab);

  // Prepare the common parsing state.
  std::unique_ptr<TSParser, decltype(&ts_parser_delete)> Parser(
      ts_parser_new(), ts_parser_delete);
  ts_parser_set_language(Parser.get(), tree_sitter_cpp());

  // Process each file and emit hints.
  std::string Contents;
  for (size_t InputIndex = 0; InputIndex < InputPaths.size(); ++InputIndex) {
    const auto &InputPath = InputPaths[InputIndex];
    if (!readFile(InputPath, Contents))
      continue; // The error details are logged by the function.
    auto Tree = parseFile(Contents, Parser.get());
    if (!Tree) {
      std::cerr << "Failed to parse " << InputPath << "\n";
      continue;
    }
    auto FileId = MultiFile ? std::make_optional<int>(
                                  Vocab.size() - InputPaths.size() + InputIndex)
                            : std::nullopt;
    Transform->processFile(Contents, *Tree, FileId);
  }
  Transform->finalize();
}
