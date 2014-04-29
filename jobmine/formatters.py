def format(result):
    """
    Formats the output from the browser call into a string.

    :result    object
    :return    None
    """
    if isinstance(result, list):
        # Implicit assumping that allow lists returned are list of dictionaries
        # to be printed in a table.
        if len(result) == 0:
            return "No results found."
        else:
            return format_as_table(result,
                                   result[0].keys(),
                                   result[0].keys())
    elif isinstance(result, dict):
        return format_as(result)
    elif isinstance(result, bool):
        return 'Success' if result else 'Failed'
    else:
        return result


def format_as(data, keys=None, sort_by_key=None):
    """
    Formats a dictionary of key, value inputs into a newline separated key, value
    pair.

    :data           Dictionary of data to print
    :keys           Specific keys to show
    :sort_by_key    Boolean indicates whether or not to sort output by keys
    """
    output = ""
    items = data.items()

    if keys:
        items = filter(lambda item: item[0] in keys, items)

    if sort_by_key:
        items = sorted(items, lambda x: x[0])

    for index, (key, value) in enumerate(items):
        output += "%s:\n%s%s" % (key.title(),
                                 value,
                                 " " if index == len(data) - 1 else "\n\n")

    return output


def format_as_table(data, keys, header=None, sort_by_key=None, sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Source:
        http://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        keys - List of keys in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: Boolean)
    """
    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, add header to data
    if header:
        # Get the length of each header and create a divider based
        # on that length
        header_divider = []
        for name in header:
            header_divider.append('-' * len(name))

        # Create a list of dictionary from the keys and the header and
        # insert it at the beginning of the list. Do the same for the
        # divider and insert below the header.
        header_divider = dict(zip(keys, header_divider))
        data.insert(0, header_divider)
        header = dict(zip(keys, header))
        data.insert(0, header)

    column_widths = []
    for key in keys:
        column_widths.append(max(len(str(column[key])) for column in data))

    # Create a tuple pair of key and the associated column width for it
    key_width_pair = zip(keys, column_widths)

    format = ('%-*s   ' * len(keys)).strip() + '\n'
    formatted_data = ''
    for element in data:
        data_to_format = []
        # Create a tuple that will be used for the formatting in
        # width, value format
        for pair in key_width_pair:
            data_to_format.append(pair[1])
            data_to_format.append(element[pair[0]])
        formatted_data += (format % tuple(data_to_format))
    return formatted_data.rstrip()
