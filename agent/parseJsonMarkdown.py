import re

res = """
```json
{
  "overall_match": 80,
  "strengths": ["Python", "Django"],
  "weaknesses": ["React"],
  "recommendations": [],
  "final_summary": "The candidate has a strong foundation in Python and Django"
}
```
"""


def parse_markdown_json(response: str):
    pattern = r"```json(.*?)```"
    match = re.search(pattern, response, re.DOTALL)  # re.DOTALL allows newlines to be matched
    if match:
        json_string = match.group(1).strip()  # remove extra whitespace/newlines
        return json_string
    else:
        return response


# parse_markdown_json(res)
