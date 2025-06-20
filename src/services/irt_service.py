import numpy as np
from scipy.optimize import minimize_scalar
import json

class IRTProcessor:
    """Xử lý thuật toán IRT 1PL (Rasch Model)"""
    
    def __init__(self, theta_min=-3, theta_max=3):
        self.theta_min = theta_min
        self.theta_max = theta_max
    
    def probability_correct(self, theta, b_parameter):
        """Tính xác suất trả lời đúng theo công thức IRT 1PL"""
        return 1 / (1 + np.exp(-(theta - b_parameter)))
    
    def log_likelihood(self, theta, responses, b_parameters):
        """Tính log-likelihood function"""
        prob = self.probability_correct(theta, b_parameters)
        # Tránh log(0) bằng cách thêm epsilon nhỏ
        epsilon = 1e-10
        prob = np.clip(prob, epsilon, 1 - epsilon)
        
        return np.sum(responses * np.log(prob) + (1 - responses) * np.log(1 - prob))
    
    def estimate_theta(self, responses, b_parameters):
        """Ước lượng θ (năng lực) của học sinh"""
        if len(responses) == 0 or len(b_parameters) == 0:
            return 0.0
            
        responses = np.array(responses)
        b_parameters = np.array(b_parameters)
        
        # Tối ưu hóa để tìm θ tối đa hóa log-likelihood
        result = minimize_scalar(
            lambda theta: -self.log_likelihood(theta, responses, b_parameters),
            bounds=(self.theta_min, self.theta_max),
            method='bounded'
        )
        
        return result.x if result.success else 0.0
    
    def update_b_parameter(self, question_responses, student_thetas):
        """Cập nhật tham số b_i dựa trên kết quả học sinh"""
        if not question_responses or not student_thetas:
            return 0.0
            
        # Lấy θ của những học sinh trả lời đúng câu này
        correct_thetas = [
            theta for theta, response in zip(student_thetas, question_responses) 
            if response == 1
        ]
        
        if len(correct_thetas) == 0:
            return 0.0
            
        return np.mean(correct_thetas)
    
    def scale_to_100(self, theta):
        """Quy đổi θ về thang điểm 100"""
        return ((theta - self.theta_min) / (self.theta_max - self.theta_min)) * 100
    
    def process_submission(self, answers, questions):
        """Xử lý bài nộp của học sinh"""
        # Parse answers từ string format
        parsed_answers = self.parse_answers(answers)
        
        # Tạo response vector (1 = đúng, 0 = sai)
        responses = []
        b_parameters = []
        
        for question in questions:
            question_num = question.question_number
            student_answer = parsed_answers.get(question_num, '')
            correct_answer = question.correct_answer
            
            # Kiểm tra đúng/sai
            is_correct = self.check_answer(student_answer, correct_answer, question.question_type)
            responses.append(1 if is_correct else 0)
            b_parameters.append(question.b_parameter)
        
        # Chia thành 3 phần (40-20-40)
        part1_responses = responses[:40]
        part1_b_params = b_parameters[:40]
        
        part2_responses = responses[40:60]
        part2_b_params = b_parameters[40:60]
        
        part3_responses = responses[60:100]
        part3_b_params = b_parameters[60:100]
        
        # Tính θ cho từng phần
        theta_part1 = self.estimate_theta(part1_responses, part1_b_params)
        theta_part2 = self.estimate_theta(part2_responses, part2_b_params)
        theta_part3 = self.estimate_theta(part3_responses, part3_b_params)
        
        # Tính θ tổng
        theta_total = self.estimate_theta(responses, b_parameters)
        
        # Quy đổi về thang 100
        score_part1 = self.scale_to_100(theta_part1)
        score_part2 = self.scale_to_100(theta_part2)
        score_part3 = self.scale_to_100(theta_part3)
        total_score = self.scale_to_100(theta_total)
        
        return {
            'responses': responses,
            'theta_part1': theta_part1,
            'theta_part2': theta_part2,
            'theta_part3': theta_part3,
            'theta_total': theta_total,
            'score_part1': score_part1,
            'score_part2': score_part2,
            'score_part3': score_part3,
            'total_score': total_score,
            'parsed_answers': parsed_answers
        }
    
    def parse_answers(self, answers_text):
        """Parse đáp án từ text format"""
        parsed = {}
        
        if not answers_text:
            return parsed
            
        lines = answers_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split(' ', 1)
            if len(parts) < 2:
                continue
                
            try:
                question_num = int(parts[0])
                answer = parts[1].strip()
                parsed[question_num] = answer
            except ValueError:
                continue
                
        return parsed
    
    def check_answer(self, student_answer, correct_answer, question_type):
        """Kiểm tra đáp án đúng/sai"""
        if not student_answer or not correct_answer:
            return False
            
        student_answer = student_answer.strip().upper()
        correct_answer = correct_answer.strip().upper()
        
        if question_type == 'multiple_choice':
            # Trắc nghiệm: A, B, C, D
            return student_answer == correct_answer
            
        elif question_type == 'multiple_answer':
            # Nhiều đáp án: AC, BD, ABC...
            return student_answer == correct_answer
            
        elif question_type == 'true_false':
            # Đúng/Sai: DSDS, DDSS...
            return student_answer == correct_answer
            
        elif question_type == 'fill_number':
            # Điền số: so sánh số
            try:
                student_num = float(student_answer)
                correct_num = float(correct_answer)
                return abs(student_num - correct_num) < 0.01  # Sai số 0.01
            except ValueError:
                return False
                
        elif question_type in ['fill_text', 'drag_drop']:
            # Điền từ/kéo thả: so sánh chuỗi
            return student_answer == correct_answer
            
        return False

