FROM ubuntu:rolling
RUN apt-get update
RUN apt-get -qq install -y gcc g++ wget lsb-release wget software-properties-common gnupg git cmake flex python3-pebble python3-psutil python3-chardet python3-pytest vim unifdef
RUN wget https://apt.llvm.org/llvm.sh
RUN chmod +x llvm.sh
RUN ./llvm.sh 22
RUN apt-get install -y bolt-22 clang-22 libclang-common-22-dev libclang-22-dev mlir-22-tools llvm-22-tools libclang-common-22-dev libclang-22-dev libclang1-22 clang-format-22 python3-clang-22 clangd-22 clang-tidy-22 libomp-22-dev
RUN touch /usr/lib/llvm-22/lib/libLibcTableGenUtil.a
RUN mkdir -p /tmp/cvise/build-docker
WORKDIR /tmp/cvise/build-docker
