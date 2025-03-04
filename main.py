from langchain_core.messages import AIMessage, HumanMessage, BaseMessage,SystemMessage,ToolMessage
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode,tools_condition
from langgraph.graph import MessagesState, START, END
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langchain_core.tools.base import InjectedToolCallId
from typing_extensions import Annotated
from flask import Flask
from flask import Flask, render_template
import markdown


load_dotenv()

model_name=os.getenv("MODEL_NAME")
api_key=os.getenv("API_KEY")
endpoint=os.getenv("ENDPOINT")


from LeetCode import LeetCodeSessionManager

app = Flask(__name__)

def markdown_to_html(text):
    return markdown.markdown(
    text,
    extensions=['fenced_code', 'codehilite']
)


@app.route('/')
def home():
    return {"message":"Hello World!!! This is a flask server."}

@app.route("/leetcode")
def leetcode():

    sys_msg=SystemMessage("""You are a helpful assistant having capability to solve leetcode problems.
                    You can ask me to solve any leetcode problem.
                    You have capability to generate code, test code and submit code in leetcode.
                    If any test case failed or any error occured then you will generate code again.
                    You will first generate code and you should pass that code for test the code and and if all test cases passed then submit code. If any test case failed or any error occured then again generate the code.
                    Generate Code -> Test Code -> If passed-> Submit Code->If failed-> Generate Code And so on....
                    After successfully code submission you will get output. 
                    
                    """)

    def extract_problemStatement(state: MessagesState):
        """
        This function use to extract problem statement from leetcode using selenium.

        Returns:
        str: problem statement.
        str: python code template.
        """
        if session:
            print("Authentication successful!")
            # Perform authenticated actions
            # Get daily problem
            daily_problem = session.get_daily_problem()
            if daily_problem:
                print(f"\n📌 Today's Challenge: {daily_problem['title']}")
                session.driver.get(daily_problem['url'])
                
                if session.select_python_language():
                    session.driver.refresh()
                    details = session.get_problem_details(daily_problem["base_link"])
                    if details:
                        print(f"\n📖 Problem Statement:\n{'-'*50}")
                        print(details['description'])
                        
                        print(f"\n💻 Code Template:\n{'-'*50}")
                        print(details['python_code_template'])

                        data=f"""problem_statement:\n{details['description']}\n\npython_code_template:\n{details['python_code_template']}"""
                        return {"messages":data}
                else:
                    print("Failed to select Python language")
                    return Command(update={"messages": [HumanMessage("Failed to select Python language")]},
                goto="__end__")
            else:
                print("Failed to fetch daily problem")
                return Command(update={"messages": [HumanMessage("Failed to fetch daily problem")]},
                goto="__end__")
            
            input("Press Enter to exit...")
        else:
            print("Authentication failed")
            return Command(update={"messages": [HumanMessage("Authentication failed")]},
                goto="__end__")

    def generate_code(problem_statement:str,python_code:str):
        """
        This function use to generate code from problem statement and python code template.

        Args:
        problem_statement (str): problem statement.
        python_code (str): python code template.

        Returns:
        generated code.
        """
        prompt=f"""
        You have been provided with LeetCode problem statement and python code template.
        You have to generate code for this problem statement.
        You have to use python code template to generate code.
        Result should be a valid python code in following format: ```python [code]```.
        Problem Statement:
        {problem_statement}

        Python Code Template:
        {python_code}
    """
        code=llm.invoke(prompt)
        print("Generated Code:\n",code.content)
        return code.content

    def solve_error(problem_statement:str,error:str,code:str):
        """
        This function use to solve error in code.

        Args:
        problem_statement (str): problem statement.
        error (str): error.
        code (str): code

        Returns:
        generated code.
        """
        print("In solve error")

        prompt=f"""
        You have been provided with a problem statement, previous generated code and error.
        Your task is to update the code to solve the error.
        Result should be a valid python code in following format: ```python [code]```.

        Problem Statement:
        {problem_statement}

        Error:
        {error}

        Previous Python Code:
        {code}
    """
        code=llm.invoke(prompt)
        print("Solved Error:\n",code.content)
        return code.content


    def test_code(code:str,tool_call_id:Annotated[str,InjectedToolCallId]):
        """
        This function use to test the code against test cases in leetcode using selenium.

        Args:
        code (str): code.

        Returns:
        test_code_output:error or passed.
        """
        print("In test code:\n",code)
        test_code_response=session.test_generated_code(code)
        if "Unable to insert code in code editor." in test_code_response or "Code testing failed." in test_code_response:
            return Command(update={"messages": [ToolMessage(test_code_response,tool_call_id=tool_call_id)]},
                goto="__end__")

        return test_code_response

    def submit_code(code:str,tool_call_id:Annotated[str,InjectedToolCallId]):
        """
        This function use to submit code in leetcode using selenium.

        Args:
        code (str): code.

        Returns:
        output
        """
        print("In submit code")
        submit_code_response = session.submit_generated_code()
        if "Code submission failed." in submit_code_response:
            return Command(update={"messages": [ToolMessage(submit_code_response,tool_call_id=tool_call_id)]},
                goto="__end__")
        return submit_code_response

    def assistant(state: MessagesState):
        res=llm_with_tools.invoke([sys_msg]+state["messages"])
        print(res)
        return {"messages": res}

    llm=ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0.3,
        base_url=endpoint
    )

    tools=[generate_code,test_code,submit_code,solve_error]
    llm_with_tools=llm.bind_tools(tools)

    builder = StateGraph(MessagesState)
    builder.add_node("Extract_Problem",extract_problemStatement)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "Extract_Problem")
    builder.add_edge("Extract_Problem", "assistant")
    builder.add_conditional_edges(
        "assistant", tools_condition
    )
    builder.add_edge("tools", "assistant")

    react_graph=builder.compile()
    react_graph.get_graph().draw_mermaid_png(output_file_path="./leetcode.png")
    print(react_graph.get_graph().draw_mermaid())


    with LeetCodeSessionManager() as session:
        for chunk in react_graph.stream({"messages": [HumanMessage("Please solve todays leetcode problem")]}):
            print(chunk)
            print("---"*50)
        print(chunk["assistant"]["messages"].content)
        print("Done")
    message=chunk["assistant"]["messages"].content
    html_message = markdown_to_html(message)
    return render_template("solution.html", message=html_message)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
    
