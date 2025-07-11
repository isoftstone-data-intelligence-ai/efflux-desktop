artifacts_prompt = """
You are a skilled software engineer.
You do not make mistakes.
Generate an fragment.
You can install additional dependencies.
Do not touch project dependencies files like package.json, package-lock.json, requirements.txt, etc.
You can use one of the following templates:

1. Python data analyst: "Runs code as a Jupyter notebook cell. Strong data analysis angle. Can use complex visualisation to explain results." File: script.py. Dependencies installed: python, jupyter, numpy, pandas, matplotlib, seaborn, plotly. Port: none.
2. Next.js developer: "A Next.js 13+ app that reloads automatically. Using the pages router." File: pages/index.tsx. Dependencies installed: nextjs@14.2.5, typescript, @types/node, @types/react, @types/react-dom, postcss, tailwindcss, shadcn. Port: 3000.
3. Vue.js developer: "A Vue.js 3+ app that reloads automatically. Only when asked specifically for a Vue app." File: app.vue. Dependencies installed: vue@latest, nuxt@3.13.0, tailwindcss. Port: 3000.
4. Streamlit developer: "A streamlit app that reloads automatically." File: app.py. Dependencies installed: streamlit, pandas, numpy, matplotlib, request, seaborn, plotly. Port: 8501.
5. Gradio developer: "A gradio app. Gradio Blocks/Interface should be called demo." File: app.py. Dependencies installed: gradio, pandas, numpy, matplotlib, request, seaborn, plotly. Port: 7860.

And please provide your response in JSON format without any additional explanations or comments.
The response must follow this schema structure, with the code placed in the code field.
Use the same language matching the user's language when filling the commentary section.

schema:{
    "commentary": "I will generate a simple 'Hello World' application using the Next.js template. This will include a basic page that displays 'Hello World' when accessed.",
    "template": "nextjs-developer",
    "title": "Hello World",
    "description": "A simple Next.js app that displays 'Hello World'.",
    "additional_dependencies": [],
    "has_additional_dependencies": false,
    "install_dependencies_command": "",
    "port": 3000,
    "file_path": "pages/index.tsx",
    "code": ""
}
"""
default_agent = {
    "ppter": {
        "id": "f83b0799-366c-4b1b-8983-050ef0ebcf49",
        "name": "ppter",
        "tools_group_list": [
            {
                "group_name": "browser",
                "type": "LOCAL"
            }
        ],
        "build_in": True,
        "description": "PPT Agent"
    },
    "new_interpretation_of_chinese": {
        "id": "f83b0799-366c-4b1b-8983-050ef0ebcf50",
        "name": "汉语新解",
        "tools_group_list": [
            {
                "group_name": "browser",
                "type": "LOCAL"
            }
        ],
        "build_in": True,
        "description": "SVG Agent"
    }
}
model_settings = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com"
    },
    "amazon_bedrock": {
        "fields": {
            "AWS_ACCESS_KEY_ID": "AWS Access Key",
            "AWS_SECRET_ACCESS_KEY": "AWS Secret Key",
            "AWS_REGION": "AWS Region",
        }
    },
    "azure_openai": {
        "fields": {
            "endpoint": "Azure OpenAI Endpoint: https://isfot-ai.openai.azure.com/ (demo)",
            "subscription_key": "Azure OpenAI Subscription Key: c70ec31c1d794452a5e18eefb0e**** (demo)",
            "api_version": "Azure OpenAI API Version: 2024-12-01-preview (demo)"
        }
    }
}