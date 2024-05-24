def produce_functions_timepoints(events):
    functions_timepoints = []
    call_stack = []
    sorted_events = sorted(events, reverse=True, key=lambda e: (e[2], e[0]))
    while len(sorted_events) > 0:
        event = sorted_events.pop()
        if event[1] == "start":
            if len(call_stack) > 0:
                prev_function_call = call_stack.pop()
                prev_function_call[1].append((event[2], "paused"))
                call_stack.append(prev_function_call)
            new_function_call = [event[0], [(event[2], "start")]]
            call_stack.append(new_function_call)
        elif event[1] == "end":
            if len(call_stack) == 0:
                raise Exception("This is not a valid call stack")
            function_call = call_stack.pop()
            if event[0] != function_call[0]:
                raise Exception("This is not a valid call stack")
            function_call[1].append((event[2], "end"))
            functions_timepoints.append(function_call)
            if len(call_stack) > 0:
                prev_function_call = call_stack.pop()
                prev_function_call[1].append((event[2], "start"))
                call_stack.append(prev_function_call)
    return functions_timepoints


def calculate_functions_duration(timepoints):
    durations = []
    for function_timelist in timepoints:
        duration = 0
        for i in range(len(function_timelist[1]) - 1):
            if (function_timelist[1][i + 1][1] == "paused" or function_timelist[1][i + 1][1] == "end") and \
                    function_timelist[1][i][1] == "start":
                duration += function_timelist[1][i + 1][0] - function_timelist[1][i][0]
        durations.append((function_timelist[0], duration))
    return durations


def functions_call_duration(events):
    durations = []
    functions_timepoints = produce_functions_timepoints(events)
    if len(functions_timepoints) > 0:
        durations = calculate_functions_duration(functions_timepoints)
    return durations


if __name__ == '__main__':
    #in_list = [("f", "start", 0), ("g", "start", 2), ("g", "end", 4), ("f", "end", 6)]
    #in_list = [("f", "start", 0), ("g", "start", 1), ("h1", "start", 2), ("h1", "end", 3), ("h2", "start", 4),
    #("h2", "end", 6), ("g", "end", 8), ("f", "end", 10)]
    #in_list = [("f", "start", 0), ("f", "end", 4), ("g", "start", 4), ("g", "end", 6)]
    #in_list = [("f", "start", 0), ("f", "end", 2), ("g", "start", 1), ("g", "end", 6)]
    #in_list = [("f", "start", 0), ("f", "end", 2), ("f", "start", 1), ("f", "end", 6)]
    #in_list = [("f", "start", 0), ("g", "end", 1)]
    in_list = [("f", "start", 0), ("f", "end", 4), ("g", "start", 5), ("g", "end", 1)]
    print(produce_functions_timepoints(in_list))
    out_list = functions_call_duration(in_list)
    print(out_list)
