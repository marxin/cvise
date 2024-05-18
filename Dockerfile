FROM ubuntu:23.10
RUN apt-get update
RUN apt-get -qq install -y gcc g++ wget lsb-release wget software-properties-common gnupg git cmake flex python3-pebble python3-psutil python3-chardet python3-pytest vim unifdef
RUN wget https://apt.llvm.org/llvm.sh
RUN chmod +x llvm.sh
RUN ./llvm.sh 19
RUN apt-get install -y bolt-19 clang-19 libclang-common-19-dev libclang-19-dev mlir-19-tools llvm-19-tools libclang-common-19-dev libclang-19-dev libclang1-19 clang-format-19 python3-clang-19 clangd-19 clang-tidy-19 libomp-19-dev
RUN mkdir -p /tmp/cvise/build-docker
WORKDIR /tmp/cvise/build-docker
