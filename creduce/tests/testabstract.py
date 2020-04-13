from creduce.passes.abstract import PassResult

def iterate_pass(current_pass, path):
    state = current_pass.new(path)
    while state != None:
        (result, state) = current_pass.transform(path, state)
        if result == PassResult.OK:
            state = current_pass.advance_on_success(path, state)
        else:
            state = current_pass.advance(path, state)
