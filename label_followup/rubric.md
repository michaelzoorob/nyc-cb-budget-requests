# Follow-up actions for NYC community board budget requests

Each record holds the city's two responses to a community board budget request. The **agency response** comes first, in January. The **OMB Executive response** comes in April or May with the Executive Budget. Decide the most useful next step for a community board that still wants the request.

Label the responses, not the request. The same pair of responses can answer many different requests, so do not assume anything about what was requested beyond what the responses say.

## action

Pick exactly one. Use these names verbatim.

- **Contact agency.** The next step is a conversation with the responsible agency. The responses ask the board to contact the agency or a named office (a Borough Commissioner's office, a unit, a phone number or email). Or the agency needs more information from the board, did not understand the request, says further study or investigation is needed, funds only part of a request with several parts, or does not support the request for reasons other than money.
- **Contact elected officials.** Council Members and the Borough President can help. They allocate capital funds (Reso A) and expense (discretionary) funds, advocate in the budget, and pass legislation. Use this when the agency supports the request or finds merit but lacks funds, when funding is uncertain or not prioritized, when the request is not recommended for funding, when approval depends on funds the agency does not control, when a response recommends bringing the request to elected officials, or when the request needs new legislation or a decision beyond the agency.
- **Contact agency and elected officials.** Both steps are clearly called for. For example, the agency supports the request and lacks funds, and it also asks the board to contact it or to supply details.
- **Track with agency.** The agency has agreed or acted. It will accommodate the request within existing resources, supports and can accommodate it, has funded or scheduled it, or has increased funding in that area. The board's next step is to check on progress later.
- **Use 311 or another channel.** A response says this is not a budget request, or points to 311, a service request, an online form, a permit or program application, or a process (such as ARTS or a grant program) that handles it. A response that points to a different agency is Contact agency with the purpose redirect.
- **No follow-up needed.** The request is completed, or fully funded and done, and nothing remains to ask.

## Which statement decides

Decide from the most specific statement in either response. A statement that gives a reason or a next step outweighs a generic one. Reasons and next steps include that the request is completed, not needed or already funded; that the agency needs more information; an instruction to contact a named office; and a recommendation to bring the request to elected officials.

- OMB text that only restates or endorses the agency ("OMB supports the agency's position", "The agency has stated that it will try to accommodate this request") defers to the agency response.
- When OMB states a new position of its own, such as recommending the request to elected officials, OMB decides.
- A specific agency reason outweighs a generic OMB funding line. If the agency says the item is in good condition and not needed, and OMB says only "not recommended for funding", the agency's reason decides.
- When a response asks the board to contact the agency or a named office, the purpose is discuss, even when the agency also declines the request. Use reconsider only when the agency declines for a stated reason other than money and gives no contact instruction.
- When the agency funds only part of a request with several parts, the action is Contact agency and the purpose is discuss.
- When the request needs new legislation or a decision by the State, the federal government or another body, the action is Contact elected officials and the purpose is advocacy.
- "Agency supports but cannot accommodate" means the agency will not do it now. It is Track with agency only when OMB states that the request is funded or scheduled. Otherwise the action is Contact elected officials (funding) when money is the obstacle, and Contact agency when the response gives another reason or asks the board to get in touch.
- OMB's stock line "The agency has stated that they will try to accommodate this request with existing resources" does not override an agency response that says it cannot accommodate the request.
- "Agency does not support but can address the need alternatively" is Track with agency when the response says what the agency will do instead, and Contact agency when it does not.
- When the agency says a project is already funded or in its ten-year plan, and OMB adds only a generic line about uncertain funds, the agency's statement decides and the action is Track with agency.
- When a response says a different agency, office or public body handles the request ("This request is for the Parks department", "Please reach out to DEP", "Contact OMB's Community Board Unit"), the action is Contact agency, the purpose is redirect, and the agency field names that body. Each record lists in "agencies" the agencies that gave this pair of responses, so a redirect names a body outside that list. A response that points to an office within the same agency (a Borough Commissioner's office, a unit) is not a redirect.
- When one response is blank, use the other. When both are blank, the action is Contact agency.

## purpose

Pick exactly one. It shapes the letter the board sends.

| purpose | use when | usual action |
| --- | --- | --- |
| clarify | the agency did not understand the request, or needs more information from the board | Contact agency |
| study | further study or investigation by the agency is needed | Contact agency |
| discuss | a response asks the board to contact the agency or a named office | Contact agency |
| reconsider | the agency does not support the request for reasons other than money | Contact agency |
| redirect | a response says a different agency, office or public body handles the request | Contact agency |
| funding | money is the obstacle | Contact elected officials, or Contact agency and elected officials |
| advocacy | the request needs legislation or a decision beyond the agency | Contact elected officials, or Contact agency and elected officials |
| status | the agency agreed, funded or scheduled it | Track with agency |
| channel | 311 or another named channel handles it | Use 311 or another channel |
| no_response | both responses are blank | Contact agency |
| none | nothing remains to ask | No follow-up needed |

## Other fields

- **why**: 5 to 15 words naming what in the responses decides it, for example "DPR lacks funds and recommends raising it with elected officials."
- **contact**: when a response names a specific office, person, phone number or email to contact, copy it (at most 20 words). Otherwise omit.
- **url**: when a response gives a URL to use, copy it exactly. Otherwise omit.
- **agency**: only with the purpose redirect. Name the body the response points to, using the exact name from this list when it is on it: Administration for Children's Services; Brooklyn Public Library; City University of New York; Citywide Event Coordination & Management; Commission on Human Rights; Community Assistance Unit; Department for the Aging; Department of Buildings; Department of City Planning; Department of Citywide Administrative Services; Department of Cultural Affairs; Department of Education; Department of Environmental Protection; Department of Finance; Department of Homeless Services; Department of Parks & Recreation; Department of Sanitation; Department of Transportation; Dept. of Consumer & Worker Protection; Dept. of Health & Mental Hygiene; District Attorney Kings Co.; District Attorney New York; Economic Development Corporation; Fire Department; Housing Preservation & Development; Human Resources Administration; Landmarks Preservation Commission; MTA / NYC Transit; Mayor's Office of Criminal Justice; Mayor's Office of Media & Entertainment; NYC Emergency Management; NYC Health + Hospitals; NYC Housing Authority; New York Public Library; Office of Management & Budget; Office of Technology & Innovation (DoITT); Police Department; Queens Public Library; School Construction Authority; Small Business Services; Special Enforcement; Taxi and Limousine Commission; Youth & Community Development. Otherwise write the body's name as the response gives it (for example "NYS Department of Transportation" or "Con Edison").

## Output

For each record return `id`, `action`, `purpose` and `why`, plus `contact`, `url` and `agency` when they apply.
